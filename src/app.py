import streamlit as st
import tomli
from pathlib import Path
from database.mongodb import db
import admin.admin_dashboard as admin_dashboard
import student.student_dashboard as student_dashboard
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def load_secrets():
    """Load secrets from Streamlit secrets or local file"""
    try:
        # First try to get secrets from Streamlit's secrets manager (for cloud deployment)
        secrets = {
            "admin_username": st.secrets["admin_username"],
            "admin_password": st.secrets["admin_password"]
        }
        return secrets
    except Exception:
        # Fallback to local file (for development)
        try:
            secrets_path = Path(__file__).parent / '.streamlit' / 'secrets.toml'
            with open(secrets_path, 'rb') as f:
                return tomli.load(f)
        except Exception as e:
            raise Exception("Failed to load secrets from both Streamlit Cloud and local file") from e

def check_admin_credentials(username, password):
    """Check if the provided credentials match admin credentials"""
    secrets = load_secrets()
    return (username == secrets["admin_username"] and
            password == secrets["admin_password"])

def check_db_connection():
    """Check if MongoDB connection is working"""
    try:
        # Try to execute a simple command to test the connection
        db.client.admin.command('ping')
        return True
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {str(e)}")
        return False

def show_login():
    st.title("Programming Contest Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            # Check admin credentials
            if check_admin_credentials(username, password):
                st.session_state.user_role = "admin"
                st.session_state.student_id = None
                st.rerun()
            else:
                # Check student credentials
                user = db.users.find_one({
                    "username": username,
                    "password": password,
                    "role": "student"
                })
                
                if user:
                    st.session_state.user_role = "student"
                    st.session_state.student_id = user["_id"]
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password!")

def main():
    # Initialize session state if not exists
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'student_id' not in st.session_state:
        st.session_state.student_id = None
    if 'test_started' not in st.session_state:
        st.session_state.test_started = False
    if 'test_completed' not in st.session_state:
        st.session_state.test_completed = False
    
    # Set page config
    st.set_page_config(
        page_title="Programming Contest App",
        page_icon="🏆",
        layout="wide"
    )
    
    # Check MongoDB connection
    if not check_db_connection():
        return
    
    # Show appropriate dashboard based on user role
    if st.session_state.user_role is None:
        show_login()
    elif st.session_state.user_role == "admin":
        admin_dashboard.show_dashboard()
    elif st.session_state.user_role == "student":
        student_dashboard.show_dashboard()

if __name__ == "__main__":
    main() 