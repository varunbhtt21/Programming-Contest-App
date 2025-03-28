import os
from pymongo import MongoClient
import streamlit as st

# Get MongoDB connection details from Streamlit secrets
MONGODB_URI = st.secrets["mongodb_uri"]
DB_NAME = st.secrets["mongodb_database"]

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