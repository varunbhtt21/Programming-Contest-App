from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
import re

# Load environment variables
load_dotenv()

def mask_password(uri):
    """Mask the password in the URI for safe printing"""
    return re.sub(r':([^@]+)@', ':****@', uri)

def test_connection():
    try:
        # Get the MongoDB URI from environment variables
        uri = os.getenv('MONGODB_URI')
        print(f"Using connection string: {mask_password(uri)}")
        print(f"Attempting to connect to MongoDB...")
        
        # Create a new client and connect to the server
        client = MongoClient(uri, server_api=ServerApi('1'))
        
        # Send a ping to confirm a successful connection
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        
        # Get database
        db = client[os.getenv('DB_NAME')]
        print(f"Connected to database: {db.name}")
        
        # List collections
        collections = db.list_collection_names()
        print(f"Available collections: {collections}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
if __name__ == "__main__":
    test_connection() 