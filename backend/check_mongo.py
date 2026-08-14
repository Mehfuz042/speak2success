from dotenv import load_dotenv
import os, sys
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
uri = os.getenv('MONGO_URI')
print('MONGO_URI=', uri)
from pymongo import MongoClient
try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print('RESULT: connected')
except Exception as e:
    print('RESULT: error')
    print(repr(e))
    sys.exit(1)
