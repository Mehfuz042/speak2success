"""Pytest fixtures for the Speak2Success backend."""
import os
import sys

# Keep the test suite offline and deterministic: never call the live Gemini API.
# (python-dotenv skips keys already present in os.environ, even when empty.)
os.environ.setdefault("GEMINI_API_KEY", "")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from app import create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _create_session(client, **overrides):
    payload = {
        "role": "Full Stack Developer",
        "skills": ["react", "flask", "mongodb"],
        "experience_years": 3,
        "coding_language": "python",
        "difficulty": "Easy",
        "coding_count": 1,
        "managerial_count": 1,
        "technical_count": 1,
        "hr_count": 1,
        "language_count": 1,
    }
    payload.update(overrides)
    res = client.post("/api/sessions", json=payload)
    return res
