import streamlit as st
from database.mongodb import db
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
import json
from bson import ObjectId
import random
import string
import io
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel("gemini-1.5-flash")

def ask_gemini(question):
    try:
        response = model.generate_content(question)
        return response.text
    except Exception as e:
        st.error(f"Error calling Gemini API: {str(e)}")
        return None

def generate_mcq_prompt(topic_prompt):
    base_prompt = f"""You are a Python instructor creating a basic test for students.
Generate 5 MCQ questions based on these topics: {topic_prompt}

Requirements:
1. All questions MUST be output-based (i.e., "What is the output of this code?")
2. Avoid nested loops and advanced concepts
3. Avoid inbuilt functions (sum(), len(), etc.) and user-defined functions
4. Keep implementation simple and beginner-friendly
5. Each question must include a 1-2 line explanation

Return ONLY a JSON object in this EXACT format:
{{
    "mcq_questions": [
        {{
            "question_text": "What is the output of this Python code:\nx = 5\ny = 2\nprint(x > y and y < 10)",
            "options": ["True", "False", "None", "Error"],
            "correct_answer": "True",
            "explanation": "Both conditions (x > y) and (y < 10) are True, so True and True equals True",
            "marks": 1
        }},
        ... 4 more questions ...
    ]
}}"""
    return base_prompt

def generate_coding_prompt(topic_prompt):
    base_prompt = f"""You are a Python instructor creating a basic test for students.
Create 1 coding problem based on these topics: {topic_prompt}

Requirements:
1. Problem should use a for/while loop with an if condition
2. Avoid nested loops and advanced concepts
3. Avoid inbuilt functions (sum(), len(), etc.) and user-defined functions
4. Include a small real-world context
5. Keep implementation simple and beginner-friendly
6. Provide sample input/output that clearly demonstrates the logic
7. Focus on mathematical pattern questions like:
   - Finding sum of factors of a number
   - Finding difference between sum of even and odd numbers in a range
   - Counting numbers divisible by specific values
   - Finding factors of a given number
   Note: Avoid list operations or nested loops as students only know basic loops with conditionals

Return ONLY a JSON object in this EXACT format:
{{
    "coding_question": {{
        "problem_statement": "Write a program to find the sum of all factors of 60.\n\nExample:\nFactors of 60 are: 1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60\nOutput should be: Sum of factors is 168",
        "sample_input": "No input needed",
        "sample_output": "Sum of factors is 168",
        "solution": "num = 60\nsum = 0\nfor i in range(1, num + 1):\n    if num % i == 0:\n        sum = sum + i\nprint('Sum of factors is', sum)",
        "explanation": "Loop through numbers 1 to 60, add number to sum if it divides 60 completely",
        "marks": 5
    }}
}}"""
    return base_prompt

def clean_json_string(json_str):
    """Clean the JSON string by removing any non-JSON content"""
    try:
        # Find the first '{' and last '}'
        start = json_str.find('{')
        end = json_str.rfind('}') + 1
        if start != -1 and end != 0:
            return json_str[start:end]
        return json_str
    except:
        return json_str

def generate_problem_set(topic_prompt):
    """Generate a complete problem set using Gemini"""
    try:
        # Generate unique set ID
        current_time = datetime.now()
        set_id = current_time.strftime("%Y-%m-%d-%H%M%S")
        
        # Generate MCQs
        mcq_response = ask_gemini(generate_mcq_prompt(topic_prompt))
        if not mcq_response:
            st.error("Failed to generate MCQ questions")
            return None
            
        # Clean and parse MCQ response
        mcq_json = clean_json_string(mcq_response)
        st.markdown("### Raw MCQ Response:")
        st.code(mcq_json, language="json")  # Debug output
        mcq_data = json.loads(mcq_json)
        
        # Generate coding question
        coding_response = ask_gemini(generate_coding_prompt(topic_prompt))
        if not coding_response:
            st.error("Failed to generate coding question")
            return None
            
        # Clean and parse coding response
        coding_json = clean_json_string(coding_response)
        st.markdown("### Raw Coding Response:")
        st.code(coding_json, language="json")  # Debug output
        coding_data = json.loads(coding_json)
        
        # Create problem set
        problem_set = {
            "mcq": {
                "type": "mcq",
                "set_id": set_id,
                "title": topic_prompt,
                "universal_prompt": topic_prompt,
                "generated_questions": mcq_data["mcq_questions"],
                "created_at": current_time
            },
            "coding": {
                "type": "coding",
                "set_id": set_id,
                "title": topic_prompt,
                "universal_prompt": topic_prompt,
                "generated_questions": [coding_data["coding_question"]],
                "created_at": current_time
            }
        }
        
        return problem_set
    except json.JSONDecodeError as e:
        st.error(f"Error parsing JSON response: {str(e)}")
        st.markdown("### Problematic Response:")
        st.code(mcq_json if 'mcq_json' in locals() else coding_json, language="json")
        return None
    except Exception as e:
        st.error(f"Error generating problem set: {str(e)}")
        return None

def get_question_set_statistics():
    """Get statistics about question sets"""
    try:
        # Get total number of MCQ sets
        total_sets = db.questions.count_documents({"type": "mcq"})
        
        # If there are no sets, return all zeros
        if total_sets == 0:
            return {
                "total_sets": 0,
                "used_sets": 0,
                "unused_sets": 0
            }
        
        # Get all test sessions to find used problem sets
        test_sessions = list(db.test_sessions.find({}, {"problem_set_id": 1}))
        used_set_ids = set()
        
        # Track used set IDs
        for session in test_sessions:
            if session.get('problem_set_id'):
                used_set_ids.add(str(session['problem_set_id']))
        
        used_sets = len(used_set_ids)
        unused_sets = total_sets - used_sets
        
        return {
            "total_sets": total_sets,
            "used_sets": used_sets,
            "unused_sets": unused_sets
        }
        
    except Exception as e:
        st.error(f"Error getting statistics: {str(e)}")
        # Return safe defaults in case of error
        return {
            "total_sets": 0,
            "used_sets": 0,
            "unused_sets": 0
        }

def manage_contest_settings():
    st.subheader("Contest Settings")
    
    # Get current settings
    settings = db.settings.find_one({"type": "contest_settings"}) or {"duration_minutes": 60}
    
    with st.form("contest_settings"):
        duration = st.number_input(
            "Contest Duration (minutes)", 
            min_value=10,
            max_value=180,
            value=settings.get("duration_minutes", 60),
            help="Set the standard duration for all contests in minutes"
        )
        
        if st.form_submit_button("Save Settings", type="primary"):
            # Update settings in database
            db.settings.update_one(
                {"type": "contest_settings"},
                {
                    "$set": {
                        "type": "contest_settings",
                        "duration_minutes": duration,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
            st.success("✨ Contest settings updated successfully!")

def show_dashboard():
    st.title("Admin Dashboard")
    
    # Add logout button and stats in sidebar
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user_role = None
        st.rerun()
    
    # Add statistics in sidebar
    stats = get_question_set_statistics()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Question Set Statistics")
    st.sidebar.metric("Total Question Sets", stats["total_sets"])
    st.sidebar.metric("Sets in Use", stats["used_sets"])
    st.sidebar.metric("Available Sets", stats["unused_sets"])
    
    if stats["unused_sets"] < 3:
        st.sidebar.warning("⚠️ Low on available question sets. Consider generating more!")
    
    # Create tabs for different sections
    tabs = st.tabs(["Generate Questions", "View Questions", "Student Management", "Test Results", "Settings"])
    
    with tabs[0]:
        generate_questions()
    
    with tabs[1]:
        view_questions(stats)  # Pass the stats to avoid recalculating
    
    with tabs[2]:
        col1, col2 = st.columns([1, 1])
        with col1:
            add_student()
        with col2:
            show_existing_students()
    
    with tabs[3]:
        view_results()
    
    with tabs[4]:
        manage_contest_settings()

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

def preview_problem_set(problem_set):
    """Display a preview of the generated problem set"""
    st.markdown("## Preview of Generated Questions")
    st.markdown(f"**Set ID:** {problem_set['mcq']['set_id']}")
    st.markdown(f"**Topic:** {problem_set['mcq']['title']}")
    
    # Preview MCQ Questions
    st.markdown("### Multiple Choice Questions")
    for i, q in enumerate(problem_set["mcq"]["generated_questions"], 1):
        st.markdown(f"\n#### Question {i}")
        
        # Split question text into regular text and code parts
        question_text = q["question_text"]
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
        
        st.markdown("**Options:**")
        for j, opt in enumerate(q["options"], 1):
            if is_code_content(opt):
                st.markdown(f"{j})")
                st.code(format_code_snippet(opt), language="python")
            else:
                st.markdown(f"{j}) {opt}")
        
        # Show answer without using an expander
        st.markdown("**✨ Correct Answer:**")
        if is_code_content(q["correct_answer"]):
            st.code(format_code_snippet(q["correct_answer"]), language="python")
        else:
            st.markdown(f"**{q['correct_answer']}**")
        st.markdown("---")
    
    # Preview Coding Question
    st.markdown("### Coding Question")
    coding_q = problem_set["coding"]["generated_questions"][0]
    st.markdown("**Problem Statement:**")
    
    # Split problem statement into text and code parts
    problem_text = coding_q["problem_statement"]
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
    
    st.markdown("\n**Sample Input:**")
    st.code(format_code_snippet(coding_q["sample_input"]), language="python")
    
    st.markdown("\n**Sample Output:**")
    st.code(format_code_snippet(coding_q["sample_output"]), language="python")
    st.markdown("---")

def generate_questions():
    st.subheader("Generate Questions")
    
    # Initialize session state for generated questions if not exists
    if 'temp_generated_sets' not in st.session_state:
        st.session_state.temp_generated_sets = []
        st.session_state.current_topic = ""
        st.session_state.num_sets = 1
    
    with st.form("generate_questions"):
        topic_prompt = st.text_area(
            "Enter the topic/concept for generating questions",
            placeholder="Example: Python data structures and algorithms, focusing on lists, dictionaries, and basic sorting algorithms"
        )
        num_sets = st.number_input("Number of problem sets to generate", min_value=1, max_value=15, value=1)
        submit = st.form_submit_button("Generate Questions")
    
    if submit and topic_prompt:
        st.session_state.temp_generated_sets = []  # Clear previous sets
        st.session_state.current_topic = topic_prompt
        st.session_state.num_sets = num_sets
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(num_sets):
            status_text.text(f"Generating problem set {i+1}/{num_sets}...")
            problem_set = generate_problem_set(topic_prompt)
            
            if problem_set:
                st.session_state.temp_generated_sets.append(problem_set)
                st.success(f"✅ Problem set {i+1} generated!")
            else:
                st.error(f"❌ Failed to generate problem set {i+1}")
            
            progress_bar.progress((i + 1) / num_sets)
    
    # Display generated sets and review buttons
    if st.session_state.temp_generated_sets:
        st.markdown("## Review Generated Problem Sets")
        st.info("Please review the generated questions and click 'Confirm' to save them or 'Regenerate' to create new ones.")
        
        # Display all generated sets
        for i, problem_set in enumerate(st.session_state.temp_generated_sets, 1):
            with st.expander(f"Problem Set {i} - {problem_set['mcq']['title']}", expanded=True):
                preview_problem_set(problem_set)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Confirm & Save", type="primary", use_container_width=True):
                successful_saves = 0
                
                # Save confirmed questions to database
                for problem_set in st.session_state.temp_generated_sets:
                    mcq_id = db.questions.insert_one(problem_set["mcq"]).inserted_id
                    coding_id = db.questions.insert_one(problem_set["coding"]).inserted_id
                    successful_saves += 1
                
                # Clear temporary storage
                st.session_state.temp_generated_sets = []
                st.session_state.current_topic = ""
                
                # Update statistics
                st.session_state.dashboard_stats = get_question_set_statistics()
                
                st.success(f"✨ Successfully saved {successful_saves} problem sets!")
                st.rerun()
        
        with col2:
            if st.button("🔄 Regenerate", type="secondary", use_container_width=True):
                # Regenerate questions with the same topic and number
                topic_prompt = st.session_state.current_topic
                num_sets = st.session_state.num_sets
                st.session_state.temp_generated_sets = []  # Clear previous sets
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i in range(num_sets):
                    status_text.text(f"Regenerating problem set {i+1}/{num_sets}...")
                    problem_set = generate_problem_set(topic_prompt)
                    
                    if problem_set:
                        st.session_state.temp_generated_sets.append(problem_set)
                        st.success(f"✅ Problem set {i+1} regenerated!")
                    else:
                        st.error(f"❌ Failed to regenerate problem set {i+1}")
                    
                    progress_bar.progress((i + 1) / num_sets)
                st.rerun()

def view_questions(stats=None):
    st.markdown("## Question Bank")
    
    # Use passed statistics if available, otherwise calculate new ones
    if stats is None:
        stats = get_question_set_statistics()
    
    # Create metrics at the top
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Question Sets", stats["total_sets"])
    with col2:
        st.metric("Sets in Use", stats["used_sets"])
    with col3:
        st.metric("Available Sets", stats["unused_sets"])
    
    # Delete All button with confirmation
    if stats["total_sets"] > 0:
        st.markdown("---")
        delete_all_col1, delete_all_col2 = st.columns([3, 1])
        with delete_all_col2:
            if st.button("🗑️ Delete All Sets", type="secondary", use_container_width=True):
                st.session_state.show_delete_confirmation = True
        
        # Show confirmation dialog
        if st.session_state.get('show_delete_confirmation', False):
            st.warning("⚠️ Are you sure you want to delete all question sets? This action cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Delete All", type="primary", use_container_width=True):
                    # Delete all test sessions first
                    db.test_sessions.delete_many({})
                    # Then delete all questions
                    db.questions.delete_many({})
                    st.session_state.show_delete_confirmation = False
                    st.session_state.dashboard_stats = get_question_set_statistics()
                    st.success("✨ All question sets and related test sessions have been deleted!")
                    st.rerun()
            with col2:
                if st.button("❌ No, Cancel", type="secondary", use_container_width=True):
                    st.session_state.show_delete_confirmation = False
                    st.rerun()
    
    st.markdown("---")
    
    # Get all questions from database
    mcq_questions = list(db.questions.find({"type": "mcq"}))
    coding_questions = list(db.questions.find({"type": "coding"}))
    
    # Get used set IDs from test sessions
    test_sessions = list(db.test_sessions.find({}, {"problem_set_id": 1}))
    used_set_ids = set()
    
    for session in test_sessions:
        if session.get('problem_set_id'):
            used_set_ids.add(str(session['problem_set_id']))
    
    st.markdown("### MCQ Questions")
    if mcq_questions:
        for q_set in mcq_questions:
            # Check if this set's ID is in use
            is_used = str(q_set['_id']) in used_set_ids
            status_color = "🔴" if is_used else "🟢"
            
            # Create columns for the set header and delete button
            col1, col2 = st.columns([5, 1])
            with col1:
                set_title = f"{status_color} **Set {q_set.get('set_id', 'Unknown ID')}:** {q_set.get('title', q_set['universal_prompt'])} ({'In Use' if is_used else 'Available'})"
                expander = st.expander(set_title)
            with col2:
                # Only show delete button for unused sets
                if not is_used:
                    if st.button("🗑️ Delete", key=f"delete_mcq_{q_set['_id']}", use_container_width=True):
                        # Delete both MCQ and coding questions for this set
                        db.questions.delete_one({"_id": q_set["_id"]})
                        db.questions.delete_one({
                            "type": "coding",
                            "universal_prompt": q_set["universal_prompt"],
                            "created_at": {
                                "$gte": q_set["created_at"] - timedelta(seconds=5),
                                "$lte": q_set["created_at"] + timedelta(seconds=5)
                            }
                        })
                        st.success(f"✨ Question set '{q_set['universal_prompt']}' deleted!")
                        st.session_state.dashboard_stats = get_question_set_statistics()
                        st.rerun()
            
            with expander:
                # Display MCQ questions
                for i, question in enumerate(q_set['generated_questions'], 1):
                    st.markdown(f"**Question {i}:** {question['question_text']}")
                    st.markdown("**Options:**")
                    for option in question['options']:
                        prefix = "✅" if option == question['correct_answer'] else "○"
                        st.markdown(f"{prefix} {option}")
                    st.markdown("---")
    else:
        st.info("No MCQ questions available")
    
    st.markdown("### Coding Questions")
    if coding_questions:
        for q_set in coding_questions:
            # Check if this set's universal prompt is in use
            is_used = str(q_set['_id']) in used_set_ids
            status_color = "🔴" if is_used else "🟢"
            
            # Create columns for the set header and delete button
            col1, col2 = st.columns([5, 1])
            with col1:
                set_title = f"{status_color} **Set {q_set.get('set_id', 'Unknown ID')}:** {q_set.get('title', q_set['universal_prompt'])} ({'In Use' if is_used else 'Available'})"
                expander = st.expander(set_title)
            with col2:
                # Only show delete button for unused sets
                if not is_used:
                    if st.button("🗑️ Delete", key=f"delete_coding_{q_set['_id']}", use_container_width=True):
                        # Delete both MCQ and coding questions for this set
                        db.questions.delete_one({"_id": q_set["_id"]})
                        db.questions.delete_one({
                            "type": "mcq",
                            "universal_prompt": q_set["universal_prompt"],
                            "created_at": {
                                "$gte": q_set["created_at"] - timedelta(seconds=5),
                                "$lte": q_set["created_at"] + timedelta(seconds=5)
                            }
                        })
                        st.success(f"✨ Question set '{q_set['universal_prompt']}' deleted!")
                        st.session_state.dashboard_stats = get_question_set_statistics()
                        st.rerun()
            
            with expander:
                # Display coding questions
                for i, question in enumerate(q_set['generated_questions'], 1):
                    st.markdown(f"**Problem {i}:**")
                    st.markdown(question['problem_statement'])
                    st.markdown("**Sample Input:**")
                    st.code(question['sample_input'])
                    st.markdown("**Sample Output:**")
                    st.code(question['sample_output'])
                    st.markdown("---")
    else:
        st.info("No coding questions available")

def generate_student_feedback(test_session, student):
    """Generate AI feedback for student performance"""
    # Prepare performance data for AI
    mcq_correct = sum(1 for attempt in test_session['question_attempts'] 
                     if isinstance(attempt['question_id'], int) and attempt['is_correct'])
    mcq_total = sum(1 for attempt in test_session['question_attempts'] 
                    if isinstance(attempt['question_id'], int))
    
    prompt = f"""As an AI tutor, provide constructive feedback for a student's programming test performance:

Student: {student['name']}
MCQ Score: {mcq_correct}/{mcq_total}
Total Score: {test_session['total_score']}/10

Question Performance:
{chr(10).join(f"- {'Correct' if attempt['is_correct'] else 'Incorrect'}: {attempt['student_answer']}" 
              for attempt in test_session['question_attempts'] if isinstance(attempt['question_id'], int))}

Coding Submission:
{test_session['question_attempts'][-1]['student_answer']}

Provide feedback in these areas:
1. Overall performance analysis
2. Specific areas of strength
3. Areas for improvement
4. Suggested learning resources
5. Next steps for improvement

Keep the feedback constructive, encouraging, and specific to their performance."""

    feedback = ask_gemini(prompt)
    return feedback if feedback else "Unable to generate feedback at this time."

def view_results():
    st.subheader("Student Results")
    
    # Get all completed test sessions with full data
    test_sessions = list(db.test_sessions.find({
        "is_completed": True
    }))
    
    if test_sessions:
        # Create summary table
        results_data = []
        for session in test_sessions:
            # Convert string ID to ObjectId if necessary
            student_id = session["student_id"]
            if isinstance(student_id, str):
                student_id = ObjectId(student_id)
            
            student = db.users.find_one({"_id": student_id})
            if student:
                # Calculate MCQ score
                mcq_correct = sum(1 for attempt in session.get('question_attempts', []) 
                                if isinstance(attempt.get('question_id'), int) and attempt.get('is_correct'))
                
                results_data.append({
                    "Name": student.get("name", "Not provided"),
                    "Email": student.get("email", "Not provided"),
                    "Score": f"{session.get('total_score', 0)}/10",
                    "MCQ Score": f"{mcq_correct}/5",
                    "Completion Time": session["end_time"].strftime("%Y-%m-%d %H:%M"),
                    "Duration": int((session["end_time"] - session["start_time"]).total_seconds() // 60),
                    "_session": session,
                    "_student": student
                })
        
        if results_data:
            # Delete All Results button with confirmation
            delete_all_col1, delete_all_col2 = st.columns([3, 1])
            with delete_all_col2:
                if st.button("🗑️ Delete All Results", type="secondary", use_container_width=True):
                    st.session_state.show_results_delete_confirmation = True
            
            # Show confirmation dialog for Delete All
            if st.session_state.get('show_results_delete_confirmation', False):
                st.warning("⚠️ Are you sure you want to delete all student results? This action cannot be undone!")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete All Results", type="primary", use_container_width=True):
                        # Delete all test sessions
                        db.test_sessions.delete_many({"is_completed": True})
                        st.session_state.show_results_delete_confirmation = False
                        st.success("✨ All student results have been deleted!")
                        st.rerun()
                with col2:
                    if st.button("❌ No, Cancel", type="secondary", use_container_width=True):
                        st.session_state.show_results_delete_confirmation = False
                        st.rerun()
            
            st.markdown("---")
            
            # Display summary table
            df = pd.DataFrame(results_data)
            display_df = df[["Name", "Email", "Score", "MCQ Score", "Completion Time", "Duration"]].copy()
            display_df.columns = ["Name", "Email", "Total Score", "MCQ Score", "Completion Time", "Duration (mins)"]
            st.dataframe(display_df, use_container_width=True)
            
            # Detailed view for each student
            st.markdown("### Detailed Results")
            for result in results_data:
                col1, col2 = st.columns([5, 1])
                with col1:
                    expander_label = f"📝 {result['Name']} - {result['Score']}"
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_result_{result['_session']['_id']}", use_container_width=True):
                        # Delete this test session
                        db.test_sessions.delete_one({"_id": result["_session"]["_id"]})
                        st.success(f"✨ Results for {result['Name']} have been deleted!")
                        st.rerun()
                
                with st.expander(expander_label):
                    session = result["_session"]
                    student = result["_student"]
                    
                    # Test Overview
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Score", result["Score"])
                    with col2:
                        st.metric("Duration", f"{result['Duration']} mins")
                    with col3:
                        st.metric("MCQ Score", result["MCQ Score"])
                    
                    # MCQ Analysis
                    st.markdown("#### MCQ Responses")
                    mcq_set = db.questions.find_one({"_id": session["problem_set_id"], "type": "mcq"})
                    
                    for attempt in session.get('question_attempts', []):
                        if isinstance(attempt.get('question_id'), int):  # MCQ question
                            status = "✅" if attempt.get('is_correct') else "❌"
                            question_num = attempt['question_id'] + 1
                            
                            # Get the original question if available
                            question_text = "Question not found"
                            correct_answer = "Answer not found"
                            if mcq_set and 0 <= attempt['question_id'] < len(mcq_set['generated_questions']):
                                q = mcq_set['generated_questions'][attempt['question_id']]
                                question_text = q['question_text']
                                correct_answer = q['correct_answer']
                            
                            st.markdown(f"{status} **Question {question_num}**")
                            st.markdown(f"Question: {question_text}")
                            st.markdown(f"Student's Answer: `{attempt['student_answer']}`")
                            if not attempt.get('is_correct'):
                                st.markdown(f"Correct Answer: `{correct_answer}`")
                            st.markdown("---")
                    
                    # Coding Submission
                    st.markdown("#### Coding Submission")
                    coding_attempt = next((attempt for attempt in session.get('question_attempts', []) 
                                        if attempt.get('question_id') == "coding_1"), None)
                    
                    # Get the original coding question
                    coding_set = db.questions.find_one({"_id": session["problem_set_id"], "type": "coding"})
                    if coding_set and coding_set['generated_questions']:
                        st.markdown("**Problem Statement:**")
                        st.markdown(coding_set['generated_questions'][0]['problem_statement'])
                        
                        st.markdown("**Expected Input/Output:**")
                        st.code(coding_set['generated_questions'][0]['sample_input'], language="python")
                        st.code(coding_set['generated_questions'][0]['sample_output'], language="python")
                    
                    if coding_attempt:
                        st.markdown("**Student's Solution:**")
                        if coding_attempt['student_answer'].strip():
                            st.code(coding_attempt['student_answer'], language="python")
                        else:
                            st.warning("No code submitted")
                    
                    # AI Feedback
                    st.markdown("#### AI Tutor Feedback")
                    if 'feedback' not in session:
                        feedback = generate_student_feedback(session, student)
                        # Store feedback in database
                        db.test_sessions.update_one(
                            {"_id": session["_id"]},
                            {"$set": {"feedback": feedback}}
                        )
                        st.markdown(feedback)
                    else:
                        st.markdown(session['feedback'])
    else:
        st.info("No test submissions yet.")

def show_existing_students():
    st.subheader("Existing Students")
    
    # Get all student users
    students = list(db.users.find({"role": "student"}))
    
    if not students:
        st.info("No students registered yet.")
        return
    
    # Create DataFrame for download
    student_data = []
    for student in students:
        # Get student's test session if any
        test_session = db.test_sessions.find_one({
            "$or": [
                {"student_id": str(student['_id'])},  # Check string ID
                {"student_id": student['_id']}  # Check ObjectId
            ]
        }, sort=[("end_time", -1)])  # Get the most recent test session
        
        data = {
            "Name": student.get('name', 'Not provided'),
            "Email": student.get('email', 'Not provided'),
            "Username": student.get('username', 'Not provided'),
            "Password": student.get('password', 'Not provided')
        }
        student_data.append(data)
    
    # Add download button at the top
    col1, col2 = st.columns([4, 1])
    with col2:
        # Convert to DataFrame
        df = pd.DataFrame(student_data)
        
        # Create Excel file in memory
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Students', index=False)
            
            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Students']
            
            # Add header formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#0E1117',
                'font_color': 'white',
                'border': 1
            })
            
            # Format headers and column widths
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                max_length = max(
                    df[value].astype(str).apply(len).max(),
                    len(value)
                )
                worksheet.set_column(col_num, col_num, max_length + 2)
        
        # Download button
        st.download_button(
            label="📥 Download Excel",
            data=buffer.getvalue(),
            file_name="student_credentials.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )
    
    st.markdown("---")
    
    # Display student list with details
    for idx, student in enumerate(students, 1):
        # Get student's test session if any
        test_session = db.test_sessions.find_one({
            "$or": [
                {"student_id": str(student['_id'])},  # Check string ID
                {"student_id": student['_id']}  # Check ObjectId
            ]
        }, sort=[("end_time", -1)])  # Get the most recent test session
        
        with st.expander(f"{idx}. {student.get('name', 'Unknown')} ({student.get('email', 'No email')})", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Student Details:**")
                st.write(f"• Name: {student.get('name', 'Not provided')}")
                st.write(f"• Email: {student.get('email', 'Not provided')}")
                st.write(f"• Registration Date: {student.get('created_at', '').strftime('%Y-%m-%d %H:%M') if student.get('created_at') else 'Not available'}")
            
            with col2:
                st.markdown("**Test Status:**")
                if test_session:
                    if test_session.get('is_completed', False):
                        st.write("• Status: ✅ Completed")
                        st.write(f"• Score: {test_session.get('total_score', 0)}/10")
                        st.write(f"• Completion Date: {test_session.get('end_time', '').strftime('%Y-%m-%d %H:%M')}")
                    else:
                        st.write("• Status: ⏳ In Progress")
                        st.write(f"• Started: {test_session.get('start_time', '').strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.write("• Status: ❌ Not Started")
            
            # Add delete button for each student
            if st.button("🗑️ Delete Student", key=f"delete_student_{student['_id']}", use_container_width=True):
                # Delete student's test sessions
                db.test_sessions.delete_many({
                    "$or": [
                        {"student_id": str(student['_id'])},
                        {"student_id": student['_id']}
                    ]
                })
                # Delete student
                db.users.delete_one({"_id": student['_id']})
                st.success(f"✨ Student {student.get('name', 'Unknown')} deleted!")
                st.rerun()

def generate_random_credentials():
    """Generate random username and password"""
    # Generate random username (e.g., student_123)
    random_number = ''.join(random.choices(string.digits, k=3))
    username = f"student_{random_number}"
    
    # Generate random password (8 characters with letters and numbers)
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    return username, password

def add_student():
    """Add a new student user with random credentials"""
    st.subheader("Add New Student")
    
    with st.form("add_student_form"):
        # Optional fields
        name = st.text_input("Name (optional)")
        email = st.text_input("Email (optional)")
        
        # Generate button
        submit = st.form_submit_button("Generate Student Account")
        
        if submit:
            # Generate random credentials
            username, password = generate_random_credentials()
            
            # Keep generating until we find a unique username
            while db.users.find_one({"username": username}):
                username, password = generate_random_credentials()
            
            # Create new student user
            new_student = {
                "username": username,
                "password": password,
                "role": "student",
                "created_at": datetime.now()
            }
            
            # Add optional fields if provided
            if name:
                new_student["name"] = name
            if email:
                new_student["email"] = email
            
            try:
                db.users.insert_one(new_student)
                st.success("✨ Student account generated successfully!")
                
                # Display the credentials
                st.info(f"""
                **Student Credentials:**
                - Username: `{username}`
                - Password: `{password}`
                
                Please save these credentials!
                """)
                
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error adding student: {str(e)}")

def show_dashboard():
    st.title("Admin Dashboard")
    
    # Add logout button and stats in sidebar
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user_role = None
        st.rerun()
    
    # Add statistics in sidebar
    stats = get_question_set_statistics()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Question Set Statistics")
    st.sidebar.metric("Total Question Sets", stats["total_sets"])
    st.sidebar.metric("Sets in Use", stats["used_sets"])
    st.sidebar.metric("Available Sets", stats["unused_sets"])
    
    if stats["unused_sets"] < 3:
        st.sidebar.warning("⚠️ Low on available question sets. Consider generating more!")
    
    # Create tabs for different sections
    tabs = st.tabs(["Generate Questions", "View Questions", "Student Management", "Test Results", "Settings"])
    
    with tabs[0]:
        generate_questions()
    
    with tabs[1]:
        view_questions(stats)  # Pass the stats to avoid recalculating
    
    with tabs[2]:
        col1, col2 = st.columns([1, 1])
        with col1:
            add_student()
        with col2:
            show_existing_students()
    
    with tabs[3]:
        view_results()
    
    with tabs[4]:
        manage_contest_settings() 