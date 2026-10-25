"""
PythonAnywhere WSGI entry point
-------------------------------
PythonAnywhere expects a wsgi.py file at the project root. This file
imports the Flask app from backend/app.py and exposes it as `application`.

After uploading, set this as your WSGI configuration file in the
PythonAnywhere Web tab:  /home/<your-username>/speak2success/wsgi.py
"""
import os
import sys

# Add the backend directory to sys.path so 'modules' can be imported.
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Set required environment variables for production.
os.environ.setdefault("PORT", "5000")
os.environ.setdefault("FLASK_DEBUG", "0")
os.environ.setdefault("STORAGE_PATH", os.path.join(_backend_dir, "data", "speak2success.sqlite3"))
os.environ.setdefault("AUDIO_DIR", os.path.join(_backend_dir, "data", "audio"))

# Import the Flask application.
from app import create_app  # noqa: E402

application = create_app()
