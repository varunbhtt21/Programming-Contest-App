import os
import tomli
from pymongo import MongoClient
import streamlit as st
from urllib.parse import quote_plus

# Load secrets using tomli
with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomli.load(f)

def get_database():
    try:
        # Use secrets loaded via tomli
        username = quote_plus(secrets["mongodb_username"])
        password = quote_plus(secrets["mongodb_password"])
        cluster = secrets["mongodb_cluster"]
        database = secrets["mongodb_database"]
        
        uri = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority"
        client = MongoClient(uri)
        db = client[database]
        initialize_collections(db)
        return db
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

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

# Initialize database instance
db = get_database()

# Export the database instance
__all__ = ['db', 'get_database'] 