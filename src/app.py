import streamlit as st
import tomli
from pathlib import Path
from database.mongodb import db
import admin.admin_dashboard as admin_dashboard
import student.student_dashboard as student_dashboard
from dotenv import load_dotenv
import os

# Set page config
st.set_page_config(
    page_title="Programming Contest App",
    page_icon="🏆",
    layout="wide"
)

# Load environment variables
load_dotenv()

def load_secrets():
    """Load secrets from Streamlit secrets or local file"""
    errors = []
    
    # Try Streamlit Cloud secrets first
    try:
        return {
            "admin_username": st.secrets.admin["username"],
            "admin_password": st.secrets.admin["password"]
        }
    except Exception as e:
        errors.append(f"Streamlit Cloud secrets error: {str(e)}")
    
    # Try local secrets file
    try:
        secrets_path = Path(__file__).parent / '.streamlit' / 'secrets.toml'
        with open(secrets_path, 'rb') as f:
            config = tomli.load(f)
            return {
                "admin_username": config["admin"]["username"],
                "admin_password": config["admin"]["password"]
            }
    except FileNotFoundError:
        errors.append(f"Local secrets.toml not found at {secrets_path}")
    except Exception as e:
        errors.append(f"Error reading local secrets: {str(e)}")
    
    # If we get here, both methods failed
    error_message = "\n".join([
        "Failed to load admin credentials. Please ensure either:",
        "",
        "1. For Streamlit Cloud deployment:",
        "   - Add secrets in Streamlit Cloud dashboard under 'Settings > Secrets'",
        "   - Required keys under [admin] section: username, password",
        "",
        "2. For local development:",
        "   - Create .streamlit/secrets.toml in the src directory",
        "   - Add required admin credentials under [admin] section",
        "",
        "Detailed errors:",
        *errors
    ])
    st.error(error_message)
    raise Exception(error_message)

def check_admin_credentials(username, password):
    """Check if the provided credentials match admin credentials"""
    try:
        secrets = load_secrets()
        return (username == secrets["admin_username"] and
                password == secrets["admin_password"])
    except Exception:
        return False

def check_db_connection():
    """Check if MongoDB connection is working"""
    if db is None:
        st.error("MongoDB connection is not available. Please check your configuration.")
        st.info("""
        To configure MongoDB:
        1. For Streamlit Cloud:
           - Go to Settings > Secrets
           - Add the following keys:
             - mongodb_username
             - mongodb_password
             - mongodb_cluster
             - mongodb_database
        
        2. For local development:
           - Create src/.streamlit/secrets.toml
           - Add the MongoDB configuration
        """)
        return False
        
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
                # Check student credentials only if db is available
                if db is not None:
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
                else:
                    st.error("❌ Database connection is not available. Please contact administrator.")

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
    
    # Check MongoDB connection
    if not check_db_connection():
        st.warning("Application functionality will be limited until database connection is restored.")
    
    # Show appropriate dashboard based on user role
    if st.session_state.user_role is None:
        show_login()
    elif st.session_state.user_role == "admin":
        if db is not None:
            admin_dashboard.show_dashboard()
        else:
            st.error("Admin dashboard is not available without database connection.")
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()
    elif st.session_state.user_role == "student":
        if db is not None:
            student_dashboard.show_dashboard()
        else:
            st.error("Student dashboard is not available without database connection.")
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()

if __name__ == "__main__":
    main() 