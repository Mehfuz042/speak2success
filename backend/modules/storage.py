"""
Storage Module
--------------
SQLite-backed persistence for interview sessions, their answers and coding
submissions. A single ``sessions`` row stores the full session document (rounds,
answers, status) as JSON, which keeps the API surface identical to the earlier
in-memory store while surviving process restarts.

When ``STORAGE_PATH`` is set (file path), data is durable on disk; otherwise an
in-memory database is used (the default for the test suite). Call ``close()``
to release the connection.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def _new_id():
    return uuid.uuid4().hex


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    role             TEXT NOT NULL,
    name             TEXT NOT NULL DEFAULT '',
    skills_json      TEXT NOT NULL DEFAULT '[]',
    experience_years INTEGER NOT NULL DEFAULT 0,
    coding_language  TEXT NOT NULL DEFAULT 'python',
    coding_difficulty TEXT NOT NULL DEFAULT 'Easy',
    resume_summary   TEXT,
    rounds_json      TEXT NOT NULL DEFAULT '[]',
    answers_json     TEXT NOT NULL DEFAULT '[]',
    review_json      TEXT,
    status           TEXT NOT NULL DEFAULT 'in_progress',
    created_at       TEXT NOT NULL,
    completed_at     TEXT
);
"""


class Storage:
    """Unified data access for sessions (answers + coding submissions included)."""

    def __init__(self, path=None):
        self._path = path if path is not None else os.environ.get("STORAGE_PATH")
        self._in_memory = not self._path or self._path == ":memory:"
        if not self._in_memory:
            parent = os.path.dirname(os.path.abspath(self._path))
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            ":memory:" if self._in_memory else self._path,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # Migration: add review_json column if upgrading from an older schema.
            try:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN review_json TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    @staticmethod
    def _dump(value):
        return json.dumps(value)

    @staticmethod
    def _load(raw, default):
        try:
            return json.loads(raw) if raw else default
        except (TypeError, ValueError):
            return default

    def _row_to_session(self, row):
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "role": row["role"],
            "name": row["name"],
            "skills": self._load(row["skills_json"], []),
            "experience_years": row["experience_years"],
            "coding_language": row["coding_language"],
            "coding_difficulty": row["coding_difficulty"],
            "rounds": self._load(row["rounds_json"], []),
            "answers": self._load(row["answers_json"], []),
            "status": row["status"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            **(
                {"resume_summary": self._load(row["resume_summary"], {})}
                if row["resume_summary"] is not None
                else {}
            ),
            **(
                {"review": self._load(row["review_json"], None)}
                if "review_json" in row.keys() and row["review_json"] is not None
                else {}
            ),
        }

    def create_session(self, user_id, role, name="", skills=None, experience_years=0,
                       coding_language="python", coding_difficulty="Easy", rounds=None,
                       resume_summary=None):
        session = {
            "id": _new_id(),
            "user_id": user_id,
            "name": name,
            "role": role,
            "skills": skills or [],
            "experience_years": experience_years,
            "coding_language": coding_language,
            "coding_difficulty": coding_difficulty,
            "rounds": rounds or [],
            "answers": [],
            "status": "in_progress",
            "created_at": _now(),
            "completed_at": None,
        }
        resume = json.dumps(resume_summary) if resume_summary is not None else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, user_id, role, name, skills_json, "
                "experience_years, coding_language, coding_difficulty, resume_summary, "
                "rounds_json, answers_json, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session["id"], user_id, role, name,
                    self._dump(session["skills"]), experience_years,
                    coding_language, coding_difficulty, resume,
                    self._dump(session["rounds"]), self._dump([]),
                    session["status"], session["created_at"],
                ),
            )
            self._conn.commit()
        return dict(session)

    def get_session(self, session_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(row) if row else None

    def add_answer(self, session_id, answer):
        """Append one answered question to a session and return the stored record."""
        doc = {"id": _new_id(), "created_at": _now()}
        doc.update(answer)
        with self._lock:
            row = self._conn.execute(
                "SELECT answers_json FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return None
            answers = self._load(row["answers_json"], [])
            answers.append(doc)
            self._conn.execute(
                "UPDATE sessions SET answers_json = ? WHERE id = ?",
                (self._dump(answers), session_id),
            )
            self._conn.commit()
        return dict(doc)

    def set_answer_audio(self, session_id, answer_id, audio_file, audio_mime):
        """Attach an uploaded audio file reference to an answer record."""
        with self._lock:
            row = self._conn.execute(
                "SELECT answers_json FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return False
            answers = self._load(row["answers_json"], [])
            target = next((a for a in answers if a["id"] == answer_id), None)
            if not target:
                return False
            target["audio_file"] = audio_file
            target["audio_mime"] = audio_mime
            self._conn.execute(
                "UPDATE sessions SET answers_json = ? WHERE id = ?",
                (self._dump(answers), session_id),
            )
            self._conn.commit()
            return True

    def complete_session(self, session_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE sessions SET status = ?, completed_at = ? WHERE id = ?",
                ("completed", _now(), session_id),
            )
            self._conn.commit()
            refreshed = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(refreshed)

    def save_review(self, session_id, review):
        """Cache a generated review so list/detail endpoints avoid re-calling Gemini."""
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET review_json = ? WHERE id = ?",
                (self._dump(review), session_id),
            )
            self._conn.commit()

    def list_sessions(self):
        """Summaries of every session, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, role, name, status, created_at, completed_at, review_json FROM sessions "
                "ORDER BY created_at DESC"
            ).fetchall()
        results = []
        for r in rows:
            s = dict(r)
            review = self._load(s.pop("review_json", None), None)
            if review:
                s["overall_score"] = review.get("overall_score")
                s["category_breakdown"] = review.get("category_breakdown")
            results.append(s)
        return results

    def delete_session(self, session_id):
        with self._lock:
            cursor = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._conn.commit()
            return cursor.rowcount > 0
