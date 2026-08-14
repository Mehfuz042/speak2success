from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
from dotenv import load_dotenv
import os
from pymongo import MongoClient

load_dotenv()

app = Flask(__name__)
CORS(app)

# Frontend static directory (workspace/frontend/public)
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public'))

# Mongo setup (optional)
MONGO_URI = os.environ.get('MONGO_URI')
mongo_client = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    except Exception:
        mongo_client = None


@app.route('/api/health')
def health():
    mongo_status = 'not-configured'
    if mongo_client:
        try:
            mongo_client.admin.command('ping')
            mongo_status = 'connected'
        except Exception as e:
            mongo_status = f'disconnected ({str(e)})'
    return jsonify({'status': 'ok', 'mongo': mongo_status})


# Serve frontend static files for non-API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # Avoid capturing API routes
    if path.startswith('api/'):
        abort(404)

    if path == '':
        filename = 'index.html'
    else:
        filename = path

    full_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(full_path):
        return send_from_directory(FRONTEND_DIR, filename)
    # Fallback to index.html for client-side routing
    return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
