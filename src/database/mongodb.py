from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv()

class MongoDB:
    def __init__(self):
        try:
            # Get MongoDB URI and database name from environment variables
            mongodb_uri = os.getenv('MONGODB_URI')
            if not mongodb_uri:
                raise ValueError("MongoDB URI not found in environment variables")
            
            # Create MongoDB client with Server API
            self.client = MongoClient(mongodb_uri, server_api=ServerApi('1'))
            
            # Test the connection
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB!")
            
            # Get database
            self.db = self.client[os.getenv('DB_NAME', 'programming_contest')]
            
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            sys.exit(1)
        except OperationFailure as e:
            print(f"Authentication failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            sys.exit(1)
        
    def get_database(self):
        return self.db
    
    def close_connection(self):
        self.client.close()

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
        sys.exit(1)

# Create database instance
mongodb = MongoDB()
db = mongodb.get_database()
initialize_collections(db) 