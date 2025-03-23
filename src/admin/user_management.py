import streamlit as st
from database.mongodb import db
import random
import string
import secrets

def generate_random_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def generate_username(name="user"):
    """Generate a unique username"""
    base = name.lower().replace(" ", "") if name else "user"
    random_suffix = ''.join(random.choices(string.digits, k=4))
    username = f"{base}{random_suffix}"
    
    # Check if username exists
    while db.users.find_one({"username": username}):
        random_suffix = ''.join(random.choices(string.digits, k=4))
        username = f"{base}{random_suffix}"
    
    return username

def manage_users():
    st.markdown("## User Management")
    
    # Create new user section
    st.markdown("### Create New Student Account")
    with st.form("create_user"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name (Optional)")
        with col2:
            email = st.text_input("Email (Optional)")
            
        # Generate username and password
        if st.form_submit_button("Generate Credentials", type="primary"):
            username = generate_username(name)
            password = generate_random_password()
            
            # Create user in database
            new_user = {
                "username": username,
                "password": password,
                "name": name,
                "email": email,
                "role": "student",
                "is_profile_complete": False
            }
            
            db.users.insert_one(new_user)
            
            # Show credentials
            st.success("✨ Student account created successfully!")
            st.code(f"""
Username: {username}
Password: {password}
            """)
            st.warning("⚠️ Make sure to save these credentials! You won't be able to see the password again.")
    
    # View and manage existing users
    st.markdown("### Existing Students")
    
    users = list(db.users.find({"role": "student"}))
    if users:
        for user in users:
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            
            with col1:
                st.markdown(f"**Username:** {user['username']}")
            with col2:
                st.markdown(f"**Name:** {user.get('name', 'Not set')}")
            with col3:
                st.markdown(f"**Email:** {user.get('email', 'Not set')}")
            with col4:
                st.markdown(f"**Profile Complete:** {'✅' if user.get('is_profile_complete') else '❌'}")
            with col5:
                if st.button("🗑️ Delete", key=f"delete_user_{user['_id']}", use_container_width=True):
                    # Delete user and their test sessions
                    db.users.delete_one({"_id": user["_id"]})
                    db.test_sessions.delete_many({"student_id": user["_id"]})
                    st.success(f"✨ User {user['username']} deleted!")
                    st.rerun()
            
            st.markdown("---")
    else:
        st.info("No students registered yet.") 