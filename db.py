from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv("MONGODB_URL")
# Hardcode the database name
HARDCODED_DB_NAME = 'dev-boaidb'

logger.info(f"Attempting to connect to hardcoded database: {HARDCODED_DB_NAME}")

if not MONGODB_URL:
    raise ValueError("MONGODB_URL must be set in the .env file")

try:
    client = MongoClient(MONGODB_URL)
    # Use the hardcoded database name
    db = client[HARDCODED_DB_NAME]
    logger.info(f"Available databases: {client.list_database_names()}")
    logger.info(f"Actually connected to database: {db.name}")
    collections = db.list_collection_names()
    logger.info(f"Collections in {db.name}: {collections}")
    
    if not collections:
        logger.warning(f"No collections found in {db.name}")
    else:
        for collection_name in collections:
            doc_count = db[collection_name].count_documents({})
            logger.info(f"Collection '{collection_name}' has {doc_count} documents")

except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

def get_db():
    return db

if __name__ == "__main__":
    # Add this to test the connection directly from this file
    test_db = get_db()
    print(f"Connected to database: {test_db.name}")
    print(f"Collections: {test_db.list_collection_names()}")