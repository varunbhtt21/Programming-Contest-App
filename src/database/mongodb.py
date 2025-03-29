import os
import tomli
from pymongo import MongoClient
from urllib.parse import quote_plus
from pathlib import Path

def load_secrets():
    """Load secrets from .streamlit/secrets.toml file"""
    secrets_path = Path(__file__).parent.parent / '.streamlit' / 'secrets.toml'
    with open(secrets_path, 'rb') as f:
        return tomli.load(f)

# Get MongoDB connection details from secrets file
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