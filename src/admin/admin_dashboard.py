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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import tomli
from pathlib import Path

# Load environment variables
load_dotenv()

def load_secrets():
    """Load secrets from Streamlit secrets or local file"""
    try:
        # First try to get secrets from Streamlit's secrets manager (for cloud deployment)
        secrets = {
            "gemini_key": st.secrets.api["gemini_key"],
            "smtp_server": st.secrets.email["server"],
            "smtp_port": st.secrets.email["port"],
            "smtp_username": st.secrets.email["username"],
            "smtp_password": st.secrets.email["password"],
            "from_email": st.secrets.email["from_addr"]
        }
        return secrets
    except Exception:
        # Fallback to local file (for development)
        try:
            secrets_path = Path(__file__).parent.parent / '.streamlit' / 'secrets.toml'
            with open(secrets_path, 'rb') as f:
                config = tomli.load(f)
                return {
                    "gemini_key": config["api"]["gemini_key"],
                    "smtp_server": config["email"]["server"],
                    "smtp_port": config["email"]["port"],
                    "smtp_username": config["email"]["username"],
                    "smtp_password": config["email"]["password"],
                    "from_email": config["email"]["from_addr"]
                }
        except Exception as e:
            raise Exception("Failed to load secrets from both Streamlit Cloud and local file") from e

# Load secrets
secrets = load_secrets()

# Configure Gemini
genai.configure(api_key=secrets["gemini_key"])
model = genai.GenerativeModel("gemini-1.5-flash")

def send_email(to_addr, subject, body):
    """Send email using SMTP configuration from secrets"""
    secrets = load_secrets()  # Reload secrets to ensure we have the latest
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = secrets["from_email"]
    msg['To'] = to_addr
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Create SMTP connection
    server = smtplib.SMTP(secrets["smtp_server"], secrets["smtp_port"])
    server.starttls()
    
    # Login and send
    server.login(secrets["smtp_username"], secrets["smtp_password"])
    server.send_message(msg)
    server.quit()

def generate_email_report(session, student):
    """Generate HTML email report for student test results"""
    
    # Calculate scores
    mcq_score = sum(
        attempt['marks_obtained'] 
        for attempt in session['question_attempts'] 
        if isinstance(attempt.get('question_id'), int)
    )
    
    coding_attempt = next(
        (attempt for attempt in session['question_attempts'] 
        if attempt.get('question_id') == "coding_1"),
        None
    )
    coding_score = coding_attempt.get('marks_obtained', 0) if coding_attempt else 0
    
    # Get MCQ responses
    mcq_responses = [
        attempt for attempt in session['question_attempts'] 
        if isinstance(attempt.get('question_id'), int)
    ]
    
    # Get coding question details
    coding_question = None
    if coding_attempt:
        coding_set_id = session.get("coding_set_id")
        if coding_set_id:
            coding_set = db.questions.find_one({"_id": coding_set_id, "type": "coding"})
            if coding_set and coding_set['generated_questions']:
                coding_question = coding_set['generated_questions'][0]
    
    # CSS styles
    css = """
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .header {
            background-color: #1a237e;
            color: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 30px;
            text-align: center;
        }
        .header h2 {
            margin: 0;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .scores {
            display: flex;
            justify-content: space-between;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .score-item {
            text-align: center;
            flex: 1;
            padding: 15px;
            border-right: 1px solid #eee;
        }
        .score-item:last-child {
            border-right: none;
        }
        .score-item h3 {
            color: #1a237e;
            margin: 0 0 10px 0;
            font-size: 18px;
        }
        .score-item p {
            font-size: 24px;
            font-weight: bold;
            margin: 0;
            color: #2196F3;
        }
        .section {
            background-color: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h3 {
            color: #1a237e;
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
            font-size: 20px;
        }
        .question {
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 6px;
        }
        .correct {
            color: #2e7d32;
            font-weight: bold;
        }
        .incorrect {
            color: #c62828;
            font-weight: bold;
        }
        code {
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 6px;
            display: block;
            white-space: pre-wrap;
            margin: 15px 0;
            font-family: 'Courier New', monospace;
            border: 1px solid #e0e0e0;
            font-size: 14px;
        }
        .problem-statement {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .score-breakdown {
            background-color: #e3f2fd;
            padding: 20px;
            border-radius: 6px;
            margin: 15px 0;
        }
        .score-breakdown h4 {
            color: #1565c0;
            margin-top: 0;
        }
        .score-breakdown ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }
        .score-breakdown li {
            padding: 8px 0;
            border-bottom: 1px solid #bbdefb;
        }
        .score-breakdown li:last-child {
            border-bottom: none;
        }
        .footer {
            text-align: center;
            padding: 20px;
            background-color: #f5f5f5;
            border-radius: 8px;
            margin-top: 30px;
            color: #666;
        }
        .summary-section {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            border-left: 4px solid #1a237e;
        }
        .summary-section h4 {
            color: #1a237e;
            margin-top: 0;
        }
        .evaluation-point {
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        .evaluation-point:last-child {
            border-bottom: none;
        }
        .evaluation-section {
            margin: 20px 0;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 6px;
        }
        
        .evaluation-section h4 {
            color: #1a237e;
            margin: 0 0 15px 0;
            font-size: 18px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 8px;
        }
        
        .score-item {
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .score-item:last-child {
            border-bottom: none;
        }
        
        .score-label {
            font-weight: bold;
            color: #1565c0;
        }
        
        .evaluation-text {
            margin: 15px 0;
            line-height: 1.6;
            color: #333;
        }
        
        .evaluation-header {
            font-weight: bold;
            color: #1565c0;
            margin: 20px 0 10px 0;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
        }
        
        .evaluation-content {
            margin: 10px 0;
            padding-left: 15px;
            border-left: 3px solid #e3f2fd;
        }
        
        .score-line {
            font-size: 16px;
            margin: 15px 0;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 6px;
        }
        
        .divider {
            border-top: 1px solid #e0e0e0;
            margin: 20px 0;
        }
        
        .evaluation-block {
            margin: 20px 0;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 6px;
        }
        
        .evaluation-title {
            font-size: 18px;
            color: #1565c0;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .evaluation-content {
            margin-left: 25px;
            line-height: 1.6;
        }
    </style>
    """
    
    # Generate HTML content
    html = f"""
    {css}
    <div class="header">
        <h2>🎓 Programming Test Report</h2>
        <p>Dear {student['name']},</p>
        <p>Here is your detailed test performance report.</p>
    </div>
    
    <div class="scores">
        <div class="score-item">
            <h3>🎯 Total Score</h3>
            <p>{session['total_score']}/10</p>
        </div>
        <div class="score-item">
            <h3>📝 MCQ Score</h3>
            <p>{mcq_score}/5</p>
        </div>
        <div class="score-item">
            <h3>💻 Coding Score</h3>
            <p>{coding_score}/5</p>
        </div>
    </div>
    
    <div class="section">
        <h3>📋 MCQ Responses</h3>
        {''.join([f'''
        <div class="question">
            <p><strong>Question {i+1}:</strong> {response.get('question_text')}</p>
            <p>Your Answer: <span class="{'correct' if response.get('is_correct') else 'incorrect'}">
                {response.get('student_answer')} {' ✅' if response.get('is_correct') else ' ❌'}
            </span></p>
            {f'<p>Correct Answer: <span class="correct">{response.get("correct_answer")}</span></p>' if not response.get('is_correct') else ''}
        </div>
        ''' for i, response in enumerate(mcq_responses)])}
    </div>
    
    <div class="section">
        <h3>🔍 Coding Problem</h3>
        {f'''
        <div class="problem-statement">
            <h4>Problem Statement:</h4>
            <p>{coding_question['problem_statement']}</p>
            
            <h4>Your Solution:</h4>
            <code>{coding_attempt.get('student_answer', 'No code submitted').strip()}</code>
            
            <div class="score-breakdown">
                <h4>Score Breakdown:</h4>
                <ul>
                    <li>🎯 Attempt Score: <strong>{coding_attempt['coding_breakdown'].get('attempt_score', 0)}/1</strong></li>
                    <li>📝 Syntax Score: <strong>{coding_attempt['coding_breakdown'].get('syntax_score', 0)}/2</strong></li>
                    <li>🧠 Logic Score: <strong>{coding_attempt['coding_breakdown'].get('logic_score', 0)}/2</strong></li>
                </ul>
            </div>
        </div>
        ''' if coding_attempt and coding_question else '<p>No coding submission found</p>'}
    </div>
    
    <div class="section">
        <h3> Detailed Summary</h3>
        <div class="summary-section">
            {session.get('feedback', 'No feedback available')
                .replace('📝 MCQ Performance Summary', '<h4>📝 MCQ Performance Summary</h4>')
                .replace('💻 Coding Performance Summary', '<h4>💻 Coding Performance Summary</h4>')
                .replace('Score Breakdown', '<div class="evaluation-header">Score Breakdown</div>')
                .replace('• Attempt Score:', '<div class="score-line">• Attempt Score:')
                .replace('---------------------------------------------', '<div class="divider"></div>')
                .replace('🎯 Attempt Score', '<div class="evaluation-block"><div class="evaluation-title">🎯 Attempt Score')
                .replace('📝 Syntax Score', '<div class="evaluation-block"><div class="evaluation-title">📝 Syntax Score')
                .replace('🧠 Logic Score', '<div class="evaluation-block"><div class="evaluation-title">🧠 Logic Score')
                .replace(')/1', ')/1</div>')
                .replace(')/2', ')/2</div>')
                .replace('• The student', '<div class="evaluation-content">• The student')
                .replace('Topics to Review:', '<div class="evaluation-header">📚 Topics to Review</div>')
                .replace('</div>\n•', '</div></div>\n•')}
        </div>
    </div>
    
    <div class="footer">
        <p>Thank you for participating in the test.</p>
        <p><strong>Best regards,<br>Jazzee Team</strong></p>
    </div>
    """
    
    return html

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
    """Display the admin dashboard"""
    st.title("Admin Dashboard")
    
    # Add logout button in sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()
    
    # Add re-evaluation option in sidebar
    with st.sidebar:
        st.markdown("### Test Management")
        revaluate_coding_submissions()
    
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
    feedback_parts = []
    
    # MCQ Analysis
    mcq_attempts = [attempt for attempt in test_session['question_attempts'] 
                   if isinstance(attempt.get('question_id'), int)]
    incorrect_mcqs = [attempt for attempt in mcq_attempts if not attempt.get('is_correct')]
    
    feedback_parts.append("📝 MCQ Performance Summary")
    if not incorrect_mcqs:
        feedback_parts.append("🎉 Congratulations! All MCQ questions were answered correctly.")
    else:
        feedback_parts.append("Topics to Review:")
        # Create prompt for Gemini to analyze incorrect MCQs
        mcq_analysis_prompt = f"""Analyze these incorrect MCQ responses and identify the Python topics the student needs to work on. Keep it brief and focused on topics only.

Questions and Answers:
{chr(10).join(f"Q: {q['question_text']}\nStudent's Answer: {q['student_answer']}\nCorrect Answer: {q['correct_answer']}" for q in incorrect_mcqs)}

Return ONLY a bullet point list of topics to review. Example:
• Variables and Data Types
• Conditional Statements
etc."""

        topics_to_review = ask_gemini(mcq_analysis_prompt)
        if topics_to_review:
            feedback_parts.append(topics_to_review)
    
    # Coding Analysis
    feedback_parts.append("\n💻 Coding Performance Summary")
    coding_attempt = next((attempt for attempt in test_session['question_attempts'] 
                         if attempt.get('question_id') == "coding_1"), None)
    
    if coding_attempt and 'coding_breakdown' in coding_attempt:
        breakdown = coding_attempt['coding_breakdown']
        
        # Score Breakdown Summary
        feedback_parts.append("\nScore Breakdown")
        feedback_parts.append(f"• Attempt Score: {breakdown['attempt_score']}/1 | Syntax Score: {breakdown['syntax_score']}/2 | Logic Score: {breakdown['logic_score']}/2")
        feedback_parts.append("\n---------------------------------------------\n")
        
        # Detailed Evaluation Summary
        evaluation_prompt = f"""Based on this code evaluation:
{breakdown['explanation']}

Format the response EXACTLY like this:

🎯 Attempt Score ({breakdown['attempt_score']}/1)
• The student demonstrated a clear understanding of the problem and made a sincere effort to develop a solution. The code submitted represents a complete, albeit possibly naive, attempt at solving the problem. There's no evidence of simply guessing or submitting incomplete or nonsensical code.

📝 Syntax Score ({breakdown['syntax_score']}/2)
• The code is free of syntax errors. The code compiles and runs without any issues related to incorrect grammar or structure of the programming language. Keywords, operators, and punctuation are used correctly. There are no typos or missing semicolons (or equivalent syntax depending on the language).

🧠 Logic Score ({breakdown['logic_score']}/2)
• The student's code correctly implements the algorithm to solve the problem. The logic accurately iterates through the required range, uses appropriate conditional statements, and calculates the result without any logical flaws. The use of the `range` function (or its equivalent) appropriately generates the sequence of numbers to iterate over."""

        detailed_evaluation = ask_gemini(evaluation_prompt)
        if detailed_evaluation:
            feedback_parts.append(detailed_evaluation)
        else:
            # Fallback to original explanation if Gemini fails
            feedback_parts.append(breakdown['explanation'])
    else:
        feedback_parts.append("❌ No coding submission found or not evaluated.")
    
    return "\n".join(feedback_parts)

def view_results():
    """View and manage test results"""
    st.title("Test Results")
    
    # Get completed test sessions
    completed_sessions = list(db.test_sessions.find({"is_completed": True}))
    
    if not completed_sessions:
        st.warning("No completed test sessions found.")
        return
    
    # Create summary table
    results_data = []
    for session in completed_sessions:
        # Convert string ID to ObjectId if needed
        student_id = session["student_id"]
        if isinstance(student_id, str):
            student_id = ObjectId(student_id)
            
        # Get student from users collection instead of students collection
        student = db.users.find_one({"_id": student_id, "role": "student"})
        if not student:
            continue
            
        # Calculate scores
        mcq_score = sum(
            attempt['marks_obtained'] 
            for attempt in session['question_attempts'] 
            if isinstance(attempt.get('question_id'), int)
        )
        
        coding_attempt = next(
            (attempt for attempt in session['question_attempts'] 
            if attempt.get('question_id') == "coding_1"),
            None
        )
        coding_score = coding_attempt.get('marks_obtained', 0) if coding_attempt else 0
        
        completion_time = session.get('end_time', '').strftime('%Y-%m-%d %H:%M:%S') if session.get('end_time') else 'Unknown'
        
        results_data.append({
            'Student Name': student.get('name', 'Unknown'),
            'Email': student.get('email', 'Not provided'),
            'Total Score': session['total_score'],
            'MCQ Score': mcq_score,
            'Coding Score': coding_score,
            'Completion Time': completion_time
        })
    
    # Display summary table
    if results_data:
        df = pd.DataFrame(results_data)
        st.dataframe(df)
    else:
        st.info("No results to display.")
    
    # Detailed view for each submission
    st.header("Detailed Submissions")
    
    for session in completed_sessions:
        # Convert string ID to ObjectId if needed
        student_id = session["student_id"]
        if isinstance(student_id, str):
            student_id = ObjectId(student_id)
            
        # Get student from users collection
        student = db.users.find_one({"_id": student_id, "role": "student"})
        if not student:
            continue
            
        with st.expander(f"View Details - {student.get('name', 'Unknown')}"):
            st.subheader("Student Information")
            st.write(f"Name: {student.get('name', 'Unknown')}")
            st.write(f"Email: {student.get('email', 'Not provided')}")
            
            # Display scores
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Score", f"{session['total_score']}/10")
            with col2:
                mcq_score = sum(
                    attempt['marks_obtained'] 
                    for attempt in session['question_attempts'] 
                    if isinstance(attempt.get('question_id'), int)
                )
                st.metric("MCQ Score", f"{mcq_score}/5")
            with col3:
                coding_attempt = next(
                    (attempt for attempt in session['question_attempts'] 
                    if attempt.get('question_id') == "coding_1"),
                    None
                )
                coding_score = coding_attempt.get('marks_obtained', 0) if coding_attempt else 0
                st.metric("Coding Score", f"{coding_score}/5")
            
            # MCQ Responses
            st.subheader("MCQ Responses")
            for attempt in session['question_attempts']:
                if isinstance(attempt.get('question_id'), int):
                    st.write(f"Question {attempt['question_id']}:")
                    st.write(f"- Question Text: {attempt.get('question_text', 'N/A')}")
                    st.write(f"- Student's Answer: {attempt.get('student_answer', 'No answer')}")
                    st.write(f"- Correct: {'✅' if attempt.get('is_correct') else '❌'}")
                    if not attempt.get('is_correct'):
                        st.write(f"- Correct Answer: {attempt.get('correct_answer', 'N/A')}")
                    st.write("---")
            
            # Coding Submission
            st.subheader("Coding Submission")
            if coding_attempt:
                coding_set_id = session.get("coding_set_id")
                if coding_set_id:
                    coding_set = db.questions.find_one({"_id": coding_set_id, "type": "coding"})
                    if coding_set and coding_set['generated_questions']:
                        coding_question = coding_set['generated_questions'][0]
                        st.write("Problem Statement:")
                        st.write(coding_question['problem_statement'])
                        st.write("Sample Input:")
                        st.code(coding_question.get('sample_input', 'Not available'))
                        st.write("Sample Output:")
                        st.code(coding_question.get('sample_output', 'Not available'))
                
                st.write("Student's Solution:")
                if coding_attempt.get('student_answer'):
                    st.code(coding_attempt['student_answer'].strip(), language='python')
                else:
                    st.warning("No code submitted")
                
                st.write("Score Breakdown:")
                breakdown = coding_attempt.get('coding_breakdown', {})
                st.write(f"- Attempt Score: {breakdown.get('attempt_score', 0)}/1")
                st.write(f"- Syntax Score: {breakdown.get('syntax_score', 0)}/2")
                st.write(f"- Logic Score: {breakdown.get('logic_score', 0)}/2")
            else:
                st.warning("No coding submission found")
            
            # AI Tutor Feedback
            st.subheader("AI Tutor Feedback")
            if session.get('feedback'):
                st.write(session['feedback'])
            else:
                st.warning("No feedback available")
            
            # Email Report Section
            st.markdown("---")
            st.subheader("📧 Send Email Report")
            
            # Generate email report
            email_body = generate_email_report(session, student)
            
            # Show email status and form
            if session.get('email_sent'):
                st.success("✉️ Email report has been sent to the student")
            
            # Always show the email form
            with st.form(key=f"email_form_{session['_id']}"):
                st.markdown("### Email Details")
                col1, col2 = st.columns([2, 1])
                with col1:
                    recipient_email = st.text_input(
                        "To:",
                        value=student.get('email', ''),
                        key=f"recipient_{session['_id']}"
                    )
                with col2:
                    cc_email = st.text_input(
                        "CC:",
                        placeholder="Multiple emails separated by comma",
                        help="You can add multiple CC recipients separated by commas (e.g., email1@example.com, email2@example.com)",
                        key=f"cc_{session['_id']}"
                    )
                
                # Add subject field
                subject = st.text_input(
                    "Subject:",
                    value=f"Test Report - {student.get('name', 'Unknown')}",
                    key=f"subject_{session['_id']}"
                )
                
                # Show email preview with edit option
                st.markdown("### 📝 Email Content")
                edited_email_body = st.text_area(
                    "Edit email content if needed:",
                    value=email_body,
                    height=500,
                    key=f"body_{session['_id']}"
                )
                
                # Submit button
                if st.form_submit_button("📤 Send Email Report", type="primary", use_container_width=True):
                    try:
                        # Process CC emails
                        cc_list = None
                        if cc_email:
                            cc_list = [email.strip() for email in cc_email.split(',') if email.strip()]
                        
                        send_email(
                            to_addr=recipient_email,
                            subject=subject,
                            body=edited_email_body
                        )
                        
                        # Update session to mark email as sent
                        db.test_sessions.update_one(
                            {"_id": session["_id"]},
                            {"$set": {"email_sent": True}}
                        )
                        
                        st.success("✨ Email report sent successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Failed to send email: {str(e)}")
                        st.info("💡 Please check the email configuration in the .env file")

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

def revaluate_coding_submissions():
    """Re-evaluate coding submissions for all existing test sessions"""
    st.subheader("Re-evaluate Coding Submissions")
    
    if st.button("Start Re-evaluation"):
        # Get all test sessions with coding submissions
        test_sessions = list(db.test_sessions.find({
            "question_attempts": {
                "$elemMatch": {
                    "question_id": "coding_1"
                }
            }
        }))
        
        if not test_sessions:
            st.info("No test sessions with coding submissions found.")
            return
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, session in enumerate(test_sessions):
            status_text.text(f"Re-evaluating submission {i+1}/{len(test_sessions)}...")
            
            # Find the coding attempt
            coding_attempt = next(
                (attempt for attempt in session['question_attempts'] 
                if attempt.get('question_id') == "coding_1"),
                None
            )
            
            if coding_attempt:
                # Check if code is actually submitted
                student_code = coding_attempt.get('student_answer', '').strip()
                if not student_code:
                    # If no code submitted, set all scores to 0
                    coding_attempt.update({
                        "is_correct": False,
                        "marks_obtained": 0,
                        "coding_breakdown": {
                            "attempt_score": 0,
                            "syntax_score": 0,
                            "logic_score": 0,
                            "explanation": "No code was submitted for evaluation."
                        }
                    })
                else:
                    # Get the original coding question using coding_set_id
                    coding_set_id = session.get("coding_set_id")
                    if not coding_set_id and "problem_set_id" in session:
                        # Fallback for old sessions: try to find coding set using problem_set_id
                        mcq_set = db.questions.find_one({"_id": session["problem_set_id"], "type": "mcq"})
                        if mcq_set:
                            coding_set = db.questions.find_one({
                                "type": "coding",
                                "universal_prompt": mcq_set["universal_prompt"],
                                "created_at": {
                                    "$gte": mcq_set["created_at"] - timedelta(seconds=5),
                                    "$lte": mcq_set["created_at"] + timedelta(seconds=5)
                                }
                            })
                            if coding_set:
                                coding_set_id = coding_set["_id"]
                                # Update session with coding_set_id for future use
                                db.test_sessions.update_one(
                                    {"_id": session["_id"]},
                                    {"$set": {"coding_set_id": coding_set_id}}
                                )
                    
                    if coding_set_id:
                        coding_set = db.questions.find_one({"_id": coding_set_id, "type": "coding"})
                        if coding_set and coding_set['generated_questions']:
                            coding_question = coding_set['generated_questions'][0]
                            
                            # Create evaluation prompt
                            evaluation_prompt = f"""Evaluate this Python code submission based on the following rubrics:

Problem Statement:
{coding_question['problem_statement']}

Student's Code:
{student_code}

Evaluation Rubrics:
1. Attempt Score (1 point):
   - 1 point if code is submitted and makes a genuine attempt to solve the problem
   - 0 points if no code submitted or submission is clearly not an attempt to solve the problem

2. Syntax Correction Score (2 points):
   - 2 points for perfect syntax
   - 1 point if 1-2 syntax errors (excluding indentation)
   - 0 points if more than 2 syntax errors

3. Code Logic Score (2 points):
   - 2 points if the code logic correctly matches the problem statement
   - 0 points if the logic doesn't match the problem statement
   Note: Code logic should solve the given problem correctly, even if there are syntax errors

Return ONLY a JSON object in this EXACT format:
{{
    "attempt_score": 0 or 1,
    "syntax_score": 0, 1, or 2,
    "logic_score": 0 or 2,
    "explanation": "Brief explanation of the scores"
}}"""

                            # Get evaluation from Gemini
                            evaluation_response = ask_gemini(evaluation_prompt)
                            if evaluation_response:
                                try:
                                    evaluation = json.loads(clean_json_string(evaluation_response))
                                    coding_score = evaluation['attempt_score'] + evaluation['syntax_score'] + evaluation['logic_score']
                                    
                                    # Update the coding attempt with new scores
                                    coding_attempt.update({
                                        "is_correct": coding_score > 0,
                                        "marks_obtained": coding_score,
                                        "coding_breakdown": {
                                            "attempt_score": evaluation['attempt_score'],
                                            "syntax_score": evaluation['syntax_score'],
                                            "logic_score": evaluation['logic_score'],
                                            "explanation": evaluation['explanation']
                                        }
                                    })
                                except json.JSONDecodeError:
                                    st.error(f"Error parsing evaluation for session {session['_id']}")
                        else:
                            st.error(f"Could not find coding question set for session {session['_id']}")
                    else:
                        st.error(f"No coding set ID found for session {session['_id']}")
                
                # Recalculate total score
                mcq_score = sum(
                    attempt['marks_obtained'] 
                    for attempt in session['question_attempts'] 
                    if isinstance(attempt.get('question_id'), int)
                )
                total_score = mcq_score + coding_attempt.get('marks_obtained', 0)
                
                # Get student info for feedback generation
                student_id = session["student_id"]
                if isinstance(student_id, str):
                    student_id = ObjectId(student_id)
                student = db.users.find_one({"_id": student_id})
                
                # Generate new AI tutor feedback
                new_feedback = generate_student_feedback(
                    {**session, "question_attempts": session['question_attempts']}, 
                    student
                )
                
                # Update the test session with new scores and feedback
                db.test_sessions.update_one(
                    {"_id": session["_id"]},
                    {
                        "$set": {
                            "question_attempts": session['question_attempts'],
                            "total_score": total_score,
                            "feedback": new_feedback
                        }
                    }
                )
            
            progress_bar.progress((i + 1) / len(test_sessions))
        
        st.success("✅ Re-evaluation completed with updated AI tutor feedback!")
        st.rerun() 