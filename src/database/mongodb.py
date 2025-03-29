import os
import tomli
from pymongo import MongoClient
from urllib.parse import quote_plus
from pathlib import Path
import streamlit as st

def load_secrets():
    """Load secrets from Streamlit secrets or local file"""
    errors = []
    
    # Try Streamlit Cloud secrets first
    try:
        return {
            "mongodb_username": st.secrets["mongodb_username"],
            "mongodb_password": st.secrets["mongodb_password"],
            "mongodb_cluster": st.secrets["mongodb_cluster"],
            "mongodb_database": st.secrets["mongodb_database"]
        }
    except Exception as e:
        errors.append(f"Streamlit Cloud secrets error: {str(e)}")
    
    # Try local secrets file
    try:
        secrets_path = Path(__file__).parent.parent / '.streamlit' / 'secrets.toml'
        with open(secrets_path, 'rb') as f:
            return tomli.load(f)
    except FileNotFoundError:
        errors.append(f"Local secrets.toml not found at {secrets_path}")
    except Exception as e:
        errors.append(f"Error reading local secrets: {str(e)}")
    
    # If we get here, both methods failed
    error_message = "\n".join([
        "Failed to load MongoDB configuration secrets. Please ensure either:",
        "",
        "1. For Streamlit Cloud deployment:",
        "   - Add secrets in Streamlit Cloud dashboard under 'Settings > Secrets'",
        "   - Required keys: mongodb_username, mongodb_password, mongodb_cluster, mongodb_database",
        "",
        "2. For local development:",
        "   - Create .streamlit/secrets.toml in the src directory",
        "   - Add required MongoDB configuration",
        "",
        "Detailed errors:",
        *errors
    ])
    st.error(error_message)
    raise Exception(error_message)

try:
    # Get MongoDB connection details from secrets
    secrets = load_secrets()
    username = secrets["mongodb_username"]
    password = secrets["mongodb_password"]
    cluster = secrets["mongodb_cluster"]
    DB_NAME = secrets["mongodb_database"]

    # Construct MongoDB URI
    MONGODB_URI = f"mongodb+srv://{username}:{password}@{cluster}/?appName=programming-contest"

    # Create MongoDB client
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    # Export the database instance
    __all__ = ['db']

    # Create collections
    def initialize_collections(db):
        """Initialize all required collections if they don't exist"""
        try:
            collections = ['users', 'questions', 'test_sessions']
            existing_collections = db.list_collection_names()
            
            for collection in collections:
                if collection not in existing_collections:
                    db.create_collection(collection)
            print("Collections initialized successfully!")
            
        except Exception as e:
            print(f"Error initializing collections: {e}")
            raise e

    # Initialize collections
    initialize_collections(db)

except Exception as e:
    st.error(f"MongoDB connection error: {str(e)}")
    # Create a dummy db object to prevent further errors
    db = None 