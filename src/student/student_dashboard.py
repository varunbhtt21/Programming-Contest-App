import streamlit as st
from database.mongodb import db
from datetime import datetime, timedelta
import random
import time
from bson.objectid import ObjectId
import pandas as pd

def get_unused_problem_set():
    """Get an unused problem set for the student"""
    try:
        # Get all MCQ sets
        all_mcq_sets = list(db.questions.find({"type": "mcq"}))
        if not all_mcq_sets:
            return None
            
        # Get all test sessions to find used problem sets
        test_sessions = list(db.test_sessions.find({}, {"problem_set_id": 1}))
        used_set_ids = set()
        
        # Track used set IDs
        for session in test_sessions:
            if session.get('problem_set_id'):
                used_set_ids.add(str(session['problem_set_id']))
        
        # Find an unused set
        for mcq_set in all_mcq_sets:
            if str(mcq_set['_id']) not in used_set_ids:
                return mcq_set
                
        # If all sets are used, return the least used one
        if all_mcq_sets:
            # Count how many times each set is used
            set_usage = {}
            for session in test_sessions:
                if session.get('problem_set_id'):
                    set_id = str(session['problem_set_id'])
                    set_usage[set_id] = set_usage.get(set_id, 0) + 1
            
            # Find the set with minimum usage
            min_usage = float('inf')
            least_used_set = None
            
            for mcq_set in all_mcq_sets:
                set_id = str(mcq_set['_id'])
                usage = set_usage.get(set_id, 0)
                if usage < min_usage:
                    min_usage = usage
                    least_used_set = mcq_set
            
            return least_used_set
        
        return None
        
    except Exception as e:
        st.error(f"Error getting unused problem set: {str(e)}")
        return None

def register_student():
    st.subheader("Student Registration")
    
    # Check if questions are available
    mcq_count = db.questions.count_documents({"type": "mcq"})
    coding_count = db.questions.count_documents({"type": "coding"})
    
    if mcq_count < 5 or coding_count < 1:
        st.error("Test is not ready yet. Please contact the administrator to set up the questions.")
        return
    
    with st.form("student_registration"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        submit = st.form_submit_button("Start Test")
        
        if submit and name and email:
            # Check if student already exists
            existing_student = db.users.find_one({"email": email})
            if existing_student:
                st.error("You have already taken the test!")
                return None
            
            # Get unused problem set
            mcq_set = get_unused_problem_set()
            if not mcq_set:
                st.error("No available problem sets. Please contact the administrator.")
                return None
            
            # Register new student
            student_data = {
                "name": name,
                "email": email,
                "role": "student",
                "created_at": datetime.now()
            }
            result = db.users.insert_one(student_data)
            
            # Create test session with assigned problem set
            session_data = {
                "student_id": str(result.inserted_id),
                "start_time": datetime.now(),
                "end_time": datetime.now() + timedelta(minutes=40),
                "is_completed": False,
                "total_score": 0,
                "problem_set_id": mcq_set['_id'],  # Use MCQ set ID as reference
                "mcq_set": mcq_set,
                "coding_set": mcq_set,
                "question_attempts": []
            }
            db.test_sessions.insert_one(session_data)
            
            st.session_state.student_id = str(result.inserted_id)
            st.session_state.test_started = True
            st.rerun()
        elif submit:
            st.error("Please fill in all fields!")

def generate_question_set():
    """Generate a unique set of questions for the student"""
    mcq_questions = list(db.questions.find({"type": "mcq"}))
    coding_questions = list(db.questions.find({"type": "coding"}))
    
    if not mcq_questions or not coding_questions:
        return None, None
    
    # Select 5 MCQs and 1 coding question
    selected_mcqs = random.sample(mcq_questions, min(5, len(mcq_questions)))
    selected_coding = random.sample(coding_questions, min(1, len(coding_questions)))
    
    return selected_mcqs, selected_coding

def format_code_snippet(code):
    """Format code snippet for display"""
    if code is None:
        return ""
    
    # Handle list input
    if isinstance(code, list):
        return "\n".join(str(item).strip() for item in code)
    
    # Handle string input
    if isinstance(code, str):
        return code.strip()
    
    # Handle any other type by converting to string
    return str(code).strip()

def is_code_content(text):
    """Check if the text contains code-like content"""
    code_indicators = [
        "```",
        "def ",
        "class ",
        "print(",
        "return ",
        "import ",
        "for ",
        "while ",
        "if ",
        "else:",
        "elif ",
        "[",  # List literals
        "{",  # Dict literals
        "lambda",
        "=",  # Assignments
        "+="
    ]
    return any(indicator in text for indicator in code_indicators)

def show_test():
    """Display the test interface for students"""
    if "test_session" not in st.session_state:
        # Try to find an active test session
        active_session = db.test_sessions.find_one({
            "student_id": st.session_state.student_id,
            "is_completed": False
        })
        
        if active_session:
            # Initialize session state with the active session
            st.session_state.test_session = active_session
            
            # Get the questions
            mcq_set = db.questions.find_one({"_id": active_session["problem_set_id"], "type": "mcq"})
            coding_set = db.questions.find_one({
                "type": "coding",
                "universal_prompt": mcq_set["universal_prompt"],
                "created_at": {
                    "$gte": mcq_set["created_at"] - timedelta(seconds=5),
                    "$lte": mcq_set["created_at"] + timedelta(seconds=5)
                }
            })
            
            st.session_state.questions = {
                'mcq': mcq_set['generated_questions'],
                'coding': coding_set['generated_questions'] if coding_set else [],
                'current_mcq': 0,
                'answers': {}
            }
        else:
            st.error("No active test session found!")
            return
    
    test_session = st.session_state.test_session
    
    # Get contest settings
    settings = db.settings.find_one({"type": "contest_settings"}) or {"duration_minutes": 60}
    contest_duration = settings.get("duration_minutes", 60)
    
    # Calculate remaining time
    if "end_time" not in st.session_state:
        st.session_state.end_time = test_session["start_time"] + pd.Timedelta(minutes=contest_duration)
    
    current_time = pd.Timestamp.now()
    remaining_time = (st.session_state.end_time - current_time).total_seconds()
    
    # Check if test time is up
    if remaining_time <= 0:
        st.warning("⚠️ Time's up! Your test will be submitted automatically.")
        submit_test()
        return
    
    # Initialize last update time if not exists
    if "last_update" not in st.session_state:
        st.session_state.last_update = current_time
    
    # Create container for timer in sidebar
    timer_container = st.sidebar.container()
    
    # Display timer
    mins, secs = divmod(int(remaining_time), 60)
    with timer_container:
        st.markdown("### ⏱️ Time Remaining")
        timer_style = "color: red;" if mins < 5 else ""
        st.markdown(f"<h2 style='text-align: center; {timer_style}'>{mins:02d}:{secs:02d}</h2>", unsafe_allow_html=True)
    
    # Only refresh every 10 seconds
    if (current_time - st.session_state.last_update).total_seconds() >= 10:
        st.session_state.last_update = current_time
        time.sleep(0.1)  # Small delay to prevent excessive CPU usage
        st.rerun()
    
    st.title("Programming Test")
    
    # Display MCQ section
    st.subheader("Multiple Choice Questions")
    current_mcq = st.session_state.questions['mcq'][st.session_state.questions['current_mcq']]
    
    # Display question number and progress
    st.progress((st.session_state.questions['current_mcq'] + 1) / 5)
    st.write(f"Question {st.session_state.questions['current_mcq'] + 1}/5:")
    
    # Display question with code formatting
    question_text = current_mcq['question_text']
    if "```" in question_text:
        parts = question_text.split("```")
        for j, part in enumerate(parts):
            if j % 2 == 0:  # Regular text
                if part.strip():
                    st.markdown(part.strip())
            else:  # Code block
                st.code(format_code_snippet(part), language="python")
    else:
        # Check if the entire question is code-like
        if is_code_content(question_text):
            st.code(format_code_snippet(question_text), language="python")
        else:
            st.markdown(question_text)
    
    # Get previous answer if it exists
    previous_answer = st.session_state.questions['answers'].get(f"mcq_{st.session_state.questions['current_mcq']}")
    
    # Create a form for the question to prevent refresh issues
    with st.form(key=f"question_form_{st.session_state.questions['current_mcq']}"):
        # Display options with code formatting
        options_container = st.container()
        with options_container:
            for i, option in enumerate(current_mcq['options']):
                if is_code_content(option):
                    st.markdown(f"Option {i + 1}:")
                    st.code(format_code_snippet(option), language="python")
        
        answer = st.radio(
            "Select your answer:",
            current_mcq['options'],
            index=current_mcq['options'].index(previous_answer) if previous_answer else 0,
            key=f"mcq_answer_{st.session_state.questions['current_mcq']}"
        )
        
        # Navigation buttons in form
        cols = st.columns([1, 2, 1])
        with cols[0]:
            prev_button = st.form_submit_button(
                "⬅️ Previous" if st.session_state.questions['current_mcq'] > 0 else "",
                disabled=st.session_state.questions['current_mcq'] == 0
            )
        
        with cols[1]:
            # Save answer button
            save_button = st.form_submit_button("💾 Save Answer")
        
        with cols[2]:
            next_button = st.form_submit_button(
                "Next ➡️" if st.session_state.questions['current_mcq'] < 4 else "",
                disabled=st.session_state.questions['current_mcq'] == 4
            )
        
        # Handle navigation and save
        if save_button:
            st.session_state.questions['answers'][f"mcq_{st.session_state.questions['current_mcq']}"] = answer
            st.success("✓ Answer saved!")
        
        if prev_button and st.session_state.questions['current_mcq'] > 0:
            st.session_state.questions['answers'][f"mcq_{st.session_state.questions['current_mcq']}"] = answer
            st.session_state.questions['current_mcq'] -= 1
            st.rerun()
        
        if next_button and st.session_state.questions['current_mcq'] < 4:
            st.session_state.questions['answers'][f"mcq_{st.session_state.questions['current_mcq']}"] = answer
            st.session_state.questions['current_mcq'] += 1
            st.rerun()
    
    # Display coding section after MCQs
    if st.session_state.questions['current_mcq'] == 4:
        st.markdown("---")
        st.subheader("Coding Question")
        coding_question = st.session_state.questions['coding'][0]
        
        # Display problem statement with code formatting
        problem_text = coding_question['problem_statement']
        if "```" in problem_text:
            parts = problem_text.split("```")
            for j, part in enumerate(parts):
                if j % 2 == 0:  # Regular text
                    if part.strip():
                        st.markdown(part.strip())
                else:  # Code block
                    st.code(format_code_snippet(part), language="python")
        else:
            st.markdown(problem_text)
        
        st.markdown("**Sample Input:**")
        st.code(format_code_snippet(coding_question['sample_input']), language="python")
        st.markdown("**Sample Output:**")
        st.code(format_code_snippet(coding_question['sample_output']), language="python")
        
        # Get previous answer if it exists
        previous_code = st.session_state.questions['answers'].get('coding')
        
        # Create a form for the coding question
        with st.form(key="coding_form"):
            code = st.text_area(
                "Write your code here:",
                value=previous_code if previous_code else "",
                height=300,
                key="coding_answer"
            )
            
            # Add a warning message about saving code
            st.info("⚠️ Make sure to save your code before submitting the test!")
            
            cols = st.columns([1, 1])
            with cols[0]:
                save_code = st.form_submit_button("💾 Save Code", use_container_width=True)
            with cols[1]:
                submit_test_button = st.form_submit_button("🏁 Submit Test", type="primary", use_container_width=True)
            
            if save_code:
                st.session_state.questions['answers']['coding'] = code
                st.success("✓ Code saved!")
            
            if submit_test_button:
                # Save the code one final time before submitting
                st.session_state.questions['answers']['coding'] = code
                score = submit_test()
                if score is not None:
                    st.success(f"✨ Test submitted successfully! Your MCQ score: {score}/5")
                    time.sleep(2)  # Give user time to see the message
                    st.rerun()
    
    # Hide Streamlit branding
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
        """, unsafe_allow_html=True)

def submit_test():
    """Submit the test and calculate score"""
    try:
        total_score = 0
        question_attempts = []
        
        # Grade MCQs
        for i, mcq in enumerate(st.session_state.questions['mcq']):
            answer = st.session_state.questions['answers'].get(f"mcq_{i}")
            is_correct = answer == mcq['correct_answer']
            total_score += 1 if is_correct else 0
            question_attempts.append({
                "question_id": i,
                "question_text": mcq['question_text'],
                "student_answer": answer,
                "correct_answer": mcq['correct_answer'],
                "is_correct": is_correct,
                "marks_obtained": 1 if is_correct else 0
            })
        
        # Store coding answer
        coding_answer = st.session_state.questions['answers'].get('coding', '')
        if st.session_state.questions['coding']:
            coding_question = st.session_state.questions['coding'][0]
            question_attempts.append({
                "question_id": "coding_1",
                "question_text": coding_question['problem_statement'],
                "student_answer": coding_answer,
                "sample_input": coding_question['sample_input'],
                "sample_output": coding_question['sample_output'],
                "is_correct": None,  # Will be evaluated by admin
                "marks_obtained": 0  # Will be updated by admin
            })
        
        # Update test session
        result = db.test_sessions.update_one(
            {
                "student_id": st.session_state.student_id,
                "is_completed": False
            },
            {
                "$set": {
                    "is_completed": True,
                    "end_time": datetime.now(),
                    "total_score": total_score,
                    "question_attempts": question_attempts,
                    "answers": st.session_state.questions['answers']
                }
            }
        )
        
        if result.modified_count == 0:
            st.error("Failed to submit test. Please try again or contact administrator.")
            return None
        
        # Clear test-related session state
        keys_to_clear = ['questions', 'end_time', 'test_session', 'last_update']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        return total_score
        
    except Exception as e:
        st.error(f"Error submitting test: {str(e)}")
        return None

def show_completed_test(test_session):
    """Show the test completion screen"""
    st.success("✨ Test Completed!")
    
    # Display completion time
    completion_time = test_session['end_time'] - test_session['start_time']
    minutes = int(completion_time.total_seconds() // 60)
    seconds = int(completion_time.total_seconds() % 60)
    st.markdown(f"**Time Taken:** {minutes} minutes {seconds} seconds")
    
    # Thank you message with email notification
    st.info("""
    Thank you for completing the test! Your responses have been recorded.
    You will receive a detailed result report through email soon.
    The administrator will review your submission and provide feedback.
    You may now close this window or logout.
    """)

def show_profile():
    """Show profile completion form"""
    st.markdown("### Complete Your Profile")
    st.info("Please complete your profile before starting the test.")
    
    # Get current user data
    student = db.users.find_one({"_id": ObjectId(st.session_state.student_id)})
    if not student:
        st.error("Student not found!")
        return False
    
    # Show form with current values if any
    with st.form("complete_profile"):
        name = st.text_input("Full Name*", value=student.get('name', ''))
        email = st.text_input("Email*", value=student.get('email', ''))
        submit = st.form_submit_button("Save Profile")
        
        if submit:
            if not name or not email:
                st.error("Both name and email are required!")
                return False
            
            # Update user profile
            db.users.update_one(
                {"_id": ObjectId(st.session_state.student_id)},
                {"$set": {"name": name, "email": email}}
            )
            st.success("✨ Profile updated successfully!")
            return True
    
    return False

def show_dashboard():
    st.title("Student Dashboard")
    
    # Add logout button
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()
    
    # Check if student exists and has completed profile
    student = db.users.find_one({"_id": ObjectId(st.session_state.student_id)})
    if not student:
        st.error("Student not found!")
        return
    
    # Check if profile is complete
    profile_complete = student.get('name') and student.get('email')
    
    if not profile_complete:
        if show_profile():
            st.rerun()  # Refresh after profile completion
        return  # Don't show test until profile is complete
    
    # First check if student has completed the test
    completed_test = db.test_sessions.find_one({
        "student_id": st.session_state.student_id,
        "is_completed": True
    })
    
    if completed_test:
        show_completed_test(completed_test)
        return
    
    # Check for active test session
    test_session = db.test_sessions.find_one({
        "student_id": st.session_state.student_id,
        "is_completed": False
    })
    
    if test_session:
        show_test()
    else:
        # Show available test button
        st.markdown("### Start Test")
        st.info("Click the button below to start your test. Make sure you have 30 minutes of uninterrupted time.")
        
        if st.button("Start Test", type="primary"):
            # Get an unused question set
            mcq_set = get_unused_problem_set()
            
            if mcq_set:
                # Create test session
                session_data = {
                    "student_id": st.session_state.student_id,
                    "start_time": datetime.now(),
                    "end_time": datetime.now() + timedelta(minutes=30),
                    "is_completed": False,
                    "total_score": 0,
                    "problem_set_id": mcq_set['_id'],  # Store only the MCQ set ID as reference
                    "question_attempts": []
                }
                
                db.test_sessions.insert_one(session_data)
                st.success("✨ Test session created! Good luck!")
                st.rerun()
            else:
                st.error("❌ No available question sets found. Please contact the administrator.")

def start_test():
    """Start a new test session for the student"""
    try:
        # Check if student already has an active test session
        existing_session = db.test_sessions.find_one({
            "student_id": st.session_state.student_id,
            "is_completed": False
        })
        
        if existing_session:
            st.session_state.test_session = existing_session
            
            # Initialize questions if not in session state
            if 'questions' not in st.session_state:
                mcq_set = db.questions.find_one({"_id": existing_session["problem_set_id"], "type": "mcq"})
                coding_set = db.questions.find_one({
                    "type": "coding",
                    "universal_prompt": mcq_set["universal_prompt"],
                    "created_at": {
                        "$gte": mcq_set["created_at"] - timedelta(seconds=5),
                        "$lte": mcq_set["created_at"] + timedelta(seconds=5)
                    }
                })
                
                st.session_state.questions = {
                    'mcq': mcq_set['generated_questions'],
                    'coding': coding_set['generated_questions'] if coding_set else [],
                    'current_mcq': 0,
                    'answers': {}
                }
            
            st.success("✨ Resuming your test session!")
            return True
        
        # Get an unused problem set
        problem_set = get_unused_problem_set()
        if not problem_set:
            st.error("No available question sets found. Please contact the administrator.")
            return False
        
        # Get contest settings
        settings = db.settings.find_one({"type": "contest_settings"}) or {"duration_minutes": 60}
        contest_duration = settings.get("duration_minutes", 60)
        
        # Create test session
        start_time = datetime.now()
        test_session = {
            "student_id": st.session_state.student_id,
            "problem_set_id": problem_set['_id'],
            "start_time": start_time,
            "end_time": start_time + timedelta(minutes=contest_duration),
            "is_completed": False,
            "total_score": 0,
            "question_attempts": []
        }
        
        # Insert test session
        result = db.test_sessions.insert_one(test_session)
        test_session['_id'] = result.inserted_id
        
        # Initialize session state
        st.session_state.test_session = test_session
        st.session_state.questions = {
            'mcq': problem_set['generated_questions'],
            'coding': [],
            'current_mcq': 0,
            'answers': {}
        }
        
        # Get corresponding coding questions
        coding_set = db.questions.find_one({
            "type": "coding",
            "universal_prompt": problem_set["universal_prompt"],
            "created_at": {
                "$gte": problem_set["created_at"] - timedelta(seconds=5),
                "$lte": problem_set["created_at"] + timedelta(seconds=5)
            }
        })
        
        if coding_set:
            st.session_state.questions['coding'] = coding_set['generated_questions']
        
        st.success("✨ Test started successfully!")
        return True
        
    except Exception as e:
        st.error(f"Error starting test: {str(e)}")
        return False 