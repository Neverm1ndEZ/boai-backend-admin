from db import get_db
from bson import ObjectId
import logging
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)
db = get_db()



def create_admin(email, password, is_super_admin=False):
    admin = {
        "email": email,
        "password": generate_password_hash(password),
        "is_super_admin": is_super_admin
    }
    return db.admins.insert_one(admin)

def get_admin_by_email(email):
    return db.admins.find_one({"email": email})

def verify_admin(email, password):
    admin = get_admin_by_email(email)
    if admin and check_password_hash(admin['password'], password):
        return admin
    return None

def is_super_admin(admin_id):
    admin = db.admins.find_one({"_id": ObjectId(admin_id)})
    return admin and admin.get('is_super_admin', False)

def get_all_collections():
    try:
        collections = db.list_collection_names()
        logger.info(f"Retrieved collections from {db.name}: {collections}")
        return collections
    except Exception as e:
        logger.error(f"Error retrieving collections from {db.name}: {e}")
        raise

def get_collection_info():
    collections = get_all_collections()
    info = []
    for collection_name in collections:
        try:
            count = db[collection_name].count_documents({})
            info.append({
                "name": collection_name,
                "count": count
            })
        except Exception as e:
            logger.error(f"Error counting documents in {collection_name}: {e}")
    return info

def get_collection_data(collection_name, limit=100):
    try:
        return list(db[collection_name].find().limit(limit))
    except Exception as e:
        logger.error(f"Error retrieving data from {collection_name}: {e}")
        raise

def get_collection_schema(collection_name):
    try:
        sample_document = db[collection_name].find_one()
        if sample_document:
            return {key: type(value).__name__ for key, value in sample_document.items()}
        return {}
    except Exception as e:
        logger.error(f"Error retrieving schema for {collection_name}: {e}")
        raise

if __name__ == "__main__":
    print(f"Database from get_db(): {db.name}")
    print("Collections:")
    collections = get_all_collections()
    if collections:
        for collection in collections:
            print(f"- {collection}")
            print(f"  Schema: {get_collection_schema(collection)}")
            print(f"  Count: {db[collection].count_documents({})}")
            print(f"  Sample document: {db[collection].find_one()}")
    else:
        print(f"No collections found in the database {db.name}.")