"""Speak2Success - Flask backend.

Run (development):
    python backend/app.py

Run (production, see Dockerfile):
    gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 \
        --bind 0.0.0.0:5000 'app:app'

The JSON REST API lives under /api/. In production the built React app
(frontend/dist) is served automatically when it exists.
"""
import base64
import json
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sock import Sock

from modules import (
    ai_config,
    body_language,
    coding_challenges,
    feedback_engine,
    job_roles,
    question_generator,
    resume_parser,
    review,
    speech_analyzer,
    storage,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("speak2success")

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
_FRONTEND_DIST = os.path.join(_PROJECT_ROOT, "frontend", "dist")
_AUDIO_DIR = os.path.join(_BACKEND_DIR, "data", "audio")

load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

DIFFICULTIES = {"Easy", "Medium", "Hard"}
ROUND_IDS = ("managerial", "technical", "hr")
ROUND_NAMES = {"managerial": "Managerial Round", "technical": "Technical Round", "hr": "HR Round"}
ROUND_CATEGORY = {"managerial": "Managerial", "technical": "Technical", "hr": "HR"}

# Content-Security-Policy for the SPA. Applies only to HTML responses served
# from the built frontend (never to /api/* or the Vite dev server).
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "connect-src 'self' ws: wss:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])


def create_app():
    """Application factory used by the dev server and the test suite."""
    app = Flask(__name__, static_folder=None)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB uploads

    origins = [
        origin.strip()
        for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    CORS(app, resources={r"/api/*": {"origins": origins}})
    sock = Sock(app)

    db = storage.Storage()
    audio_dir = os.environ.get("AUDIO_DIR") or _AUDIO_DIR

    # ---- middleware: security headers + lightweight API access log -----------

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self)")
        if not request.path.startswith("/api/") and response.mimetype == "text/html":
            response.headers.setdefault("Content-Security-Policy", _CSP)
        return response

    @app.before_request
    def log_api_request():
        request._s2s_started = datetime.now(timezone.utc)

    @app.after_request
    def log_api_access(response):
        if request.path.startswith("/api/") and response.status_code >= 500:
            elapsed = (datetime.now(timezone.utc) - request._s2s_started).total_seconds()
            log.error("%s %s -> %s (%.2fs)", request.method, request.path, response.status_code, elapsed)
        return response

    def api_error(message, status=400):
        return jsonify({"error": message}), status

    def clamp(value, low, high):
        try:
            return max(low, min(high, int(value)))
        except (TypeError, ValueError):
            return low

    # ---- health ----------------------------------------------------------

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "speak2success",
            "api_version": "0.3.0",
            "ai_provider": "gemini",
            "ai": ai_config.status(),
            "gemini_configured": ai_config.is_configured(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ---- resume -----------------------------------------------------------

    @app.post("/api/resume/parse")
    def parse_resume():
        file = request.files.get("file")
        if file is None or not file.filename:
            return api_error("Upload a PDF or TXT resume as multipart field 'file'")
        if not file.filename.lower().endswith((".pdf", ".txt", ".md")):
            return api_error("Unsupported file type — upload a PDF or TXT")
        try:
            parsed = resume_parser.parse_resume(file.stream, file.filename)
        except Exception as exc:  # noqa: BLE001 - surface a friendly message to the UI
            return api_error(f"Could not read the resume: {exc}")
        return jsonify(parsed)

    # ---- coding challenges -------------------------------------------------

    @app.get("/api/languages")
    def list_languages():
        return jsonify({"languages": coding_challenges.get_languages()})

    @app.get("/api/roles")
    def list_roles():
        return jsonify({"roles": job_roles.role_names(), "count": len(job_roles.role_names())})

    @app.get("/api/challenges")
    def list_challenges():
        language = request.args.get("language", "python")
        difficulty = request.args.get("difficulty", "").strip()
        public = coding_challenges.list_challenges(language=language)
        if difficulty:
            public = [c for c in public if c["difficulty"] == difficulty]
        return jsonify({"challenges": public, "count": len(public), "language": language})

    @app.post("/api/challenges/run")
    def run_challenge():
        data = request.get_json(silent=True) or {}
        challenge_id = (data.get("challenge_id") or "").strip()
        code = data.get("code") or ""
        language = data.get("language") or "python"
        if not challenge_id:
            return api_error("challenge_id is required")
        if not code.strip():
            return api_error("code is required")
        result, status = coding_challenges.run_submission(challenge_id, code, language=language)
        return jsonify(result), status

    # ---- questions ----------------------------------------------------------

    @app.post("/api/questions/generate")
    def generate_questions():
        data = request.get_json(silent=True) or {}
        role = (data.get("role") or "Software Engineer").strip()
        skills = data.get("skills") or []
        experience_years = clamp(data.get("experience_years"), 0, 50)
        difficulty = data.get("difficulty") if data.get("difficulty") in DIFFICULTIES else "Medium"
        category = data.get("category") or "Technical"
        count = clamp(data.get("count"), 1, 10)

        questions, source = question_generator.generate_questions(
            role=role, skills=skills, experience_years=experience_years,
            difficulty=difficulty, category=category, count=count,
        )
        if not questions:
            return api_error("Could not generate any questions", 422)
        return jsonify({"questions": questions, "source": source, "role": role})

    # ---- answer feedback / speech ---------------------------------------------

    @app.post("/api/feedback/evaluate")
    def evaluate_answer():
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        answer = (data.get("answer") or "").strip()
        if not answer:
            return api_error("answer is required")
        return jsonify(feedback_engine.evaluate_answer(question, answer))

    @app.post("/api/speech/analyze")
    def analyze_speech():
        data = request.get_json(silent=True) or {}
        transcript = data.get("transcript") or ""
        duration = float(data.get("duration_seconds") or 1)
        if not transcript.strip():
            return api_error("transcript is required")
        return jsonify(speech_analyzer.analyze_speech(transcript, duration))

    # ---- body language --------------------------------------------------------

    def _decode_frame(data):
        """Pull raw JPEG bytes from a JSON body ('frame' = base64 or data URL)."""
        frame = (data.get("frame") or "").strip()
        if not frame:
            return None, api_error("frame (base64 JPEG) is required")
        if frame.startswith("data:"):
            frame = frame.split(",", 1)[-1]
        try:
            raw = base64.b64decode(frame)
        except Exception:  # noqa: BLE001 - malformed payloads are a client bug
            return None, api_error("frame must be a base64-encoded JPEG")
        if not raw:
            return None, api_error("frame is empty")
        return raw, None

    @app.post("/api/body-language/analyze")
    def analyze_body_frame():
        data = request.get_json(silent=True) or {}
        raw, err = _decode_frame(data)
        if err is not None:
            return err
        metrics = body_language.analyze_frame(raw, timestamp_ms=int(data.get("ts_ms") or 0))
        if not metrics.get("frame_ok"):
            return api_error("; ".join(metrics.get("errors", ["invalid frame"])), 422)
        return jsonify(metrics)

    @app.post("/api/body-language/score")
    def score_body_metrics():
        """Score an aggregated per-answer body-metrics dict."""
        data = request.get_json(silent=True) or {}
        if not data:
            return api_error("body_metrics is required")
        return jsonify(body_language.analyze_body_language(data))

    @sock.route("/ws/coach")
    def ws_coach(ws):
        """Real-time coaching stream.

        Client sends raw JPEG bytes per frame; server replies with a JSON
        metrics object for each processed frame (throttle client-side to ~5fps).
        """
        while True:
            frame = ws.receive()
            if frame is None:  # client closed the socket
                break
            if not isinstance(frame, bytes | bytearray):
                continue  # ignore text/control messages
            ws.send(json.dumps(body_language.analyze_frame(bytes(frame))))

    # ---- session building helpers ------------------------------------------------

    def _pick_coding_challenges(language, difficulty, count):
        bank = coding_challenges.list_challenges(language=language)
        pool = [c for c in bank if c["difficulty"] == difficulty] or bank
        return pool[:count]

    def _build_round_questions(round_id, data):
        """Generate the questions stored inside a session for one round."""
        role = (data.get("role") or "Software Engineer").strip()
        skills = data.get("skills") or []
        experience_years = clamp(data.get("experience_years"), 0, 50)
        difficulty = data.get("difficulty") if data.get("difficulty") in DIFFICULTIES else "Medium"
        language = data.get("coding_language") or "python"

        questions = []
        if round_id == "managerial":
            count = clamp(data.get("managerial_count"), 1, 10)
            qs, _ = question_generator.generate_questions(
                role=role, skills=skills, experience_years=experience_years,
                difficulty="Medium", category="Managerial", count=count,
            )
            for q in qs:
                questions.append({**q, "type": "theory"})
        elif round_id == "technical":
            count = clamp(data.get("technical_count"), 1, 10)
            qs, _ = question_generator.generate_questions(
                role=role, skills=skills, experience_years=experience_years,
                difficulty=difficulty, category="Technical", count=count,
            )
            for q in qs:
                questions.append({**q, "type": "theory"})
            lang_qs = question_generator.generate_language_theory(
                language=language, difficulty=difficulty, count=clamp(data.get("language_count", 2), 1, 5),
            )
            for q in lang_qs:
                questions.append({**q, "type": "theory"})
            coding_count = clamp(data.get("coding_count"), 1, 3)
            for c in _pick_coding_challenges(language, difficulty, coding_count):
                questions.append({
                    "type": "coding",
                    "category": "Coding",
                    "difficulty": c["difficulty"],
                    "challenge_id": c["id"],
                    "title": c["title"],
                    "prompt": c["prompt"],
                    "starter_code": c["starter_code"],
                    "samples": c["samples"],
                    "language": language,
                })
        else:  # hr
            count = clamp(data.get("hr_count"), 1, 10)
            qs, _ = question_generator.generate_questions(
                role=role, skills=skills, experience_years=experience_years,
                difficulty="Medium", category="HR", count=count,
            )
            for q in qs:
                questions.append({**q, "type": "theory"})

        for i, q in enumerate(questions, start=1):
            q["id"] = f"{round_id}-q{i}"
        return questions

    # ---- sessions ---------------------------------------------------------

    @app.get("/api/sessions")
    def list_sessions():
        summaries = db.list_sessions()
        return jsonify({"sessions": summaries, "count": len(summaries)})

    @app.post("/api/sessions")
    def create_session():
        data = request.get_json(silent=True) or {}
        role = (data.get("role") or "Software Engineer").strip()
        if not role:
            return api_error("role is required")

        rounds = []
        for round_id in ROUND_IDS:
            rounds.append({
                "id": round_id,
                "name": ROUND_NAMES[round_id],
                "category": ROUND_CATEGORY[round_id],
                "questions": _build_round_questions(round_id, data),
            })

        session = db.create_session(
            user_id=(data.get("user_id") or "guest").strip(),
            role=role,
            name=(data.get("name") or "").strip(),
            skills=data.get("skills") or [],
            experience_years=clamp(data.get("experience_years"), 0, 50),
            coding_language=data.get("coding_language") or "python",
            coding_difficulty=data.get("difficulty") if data.get("difficulty") in DIFFICULTIES else "Easy",
            rounds=rounds,
            resume_summary=data.get("resume_summary"),
        )
        log.info("Session %s created for %s (%s)", session["id"], role, data.get("user_id") or "guest")
        return jsonify({"session": session}), 201

    @app.get("/api/sessions/<session_id>")
    def get_session(session_id):
        session = db.get_session(session_id)
        if not session:
            return api_error("Session not found", 404)
        payload = {"session": session}
        if session["status"] == "completed":
            cached = session.get("review")
            payload["review"] = cached or review.build_review(
                session["answers"], role=session["role"]
            )
        return jsonify(payload)

    @app.delete("/api/sessions/<session_id>")
    def delete_session(session_id):
        if not db.delete_session(session_id):
            return api_error("Session not found", 404)
        audio_path = os.path.join(audio_dir, session_id)
        if os.path.isdir(audio_path):
            import shutil

            shutil.rmtree(audio_path, ignore_errors=True)
        return jsonify({"deleted": session_id})

    @app.post("/api/sessions/<session_id>/answers/<answer_id>/audio")
    def upload_answer_audio(session_id, answer_id):
        session = db.get_session(session_id)
        if not session:
            return api_error("Session not found", 404)
        if not any(a["id"] == answer_id for a in session.get("answers", [])):
            return api_error("Answer not found", 404)
        file = request.files.get("audio")
        if file is None or not file.filename:
            return api_error("Upload audio as multipart field 'audio'")
        mime = (file.content_type or "audio/webm").lower()
        if not mime.startswith("audio/"):
            return api_error("Upload must be an audio file", 415)
        ext = ".webm" if "webm" in mime else ".m4a" if "mp4" in mime else ".bin"
        session_dir = os.path.join(audio_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        filename = f"{answer_id}{ext}"
        file.save(os.path.join(session_dir, filename))
        if not db.set_answer_audio(session_id, answer_id, filename, mime):
            return api_error("Could not attach audio to answer", 404)
        return jsonify({"audio_file": filename, "audio_mime": mime}), 201

    @app.get("/api/sessions/<session_id>/answers/<answer_id>/audio")
    def get_answer_audio(session_id, answer_id):
        session = db.get_session(session_id)
        if not session:
            return api_error("Session not found", 404)
        target = next((a for a in session.get("answers", []) if a["id"] == answer_id), None)
        if not target or not target.get("audio_file"):
            return api_error("No audio recorded for this answer", 404)
        path = os.path.join(audio_dir, session_id, target["audio_file"])
        if not os.path.isfile(path):
            return api_error("Audio file is missing", 404)
        return send_from_directory(
            os.path.dirname(path),
            os.path.basename(path),
            mimetype=target.get("audio_mime") or "audio/webm",
        )

    @app.post("/api/sessions/<session_id>/answers")
    def submit_answer(session_id):
        session = db.get_session(session_id)
        if not session:
            return api_error("Session not found", 404)
        if session["status"] == "completed":
            return api_error("Session already completed", 409)

        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        answer = (data.get("answer") or "").strip()
        transcript = (data.get("transcript") or "").strip()
        duration = float(data.get("duration_seconds") or 1)
        category = data.get("category") or "Technical"
        difficulty = data.get("difficulty") if data.get("difficulty") in DIFFICULTIES else "Medium"
        round_id = data.get("round_id") or ""

        text = answer or transcript
        if not text:
            return api_error("answer or transcript is required")

        speech = speech_analyzer.analyze_speech(transcript, duration) if transcript else None
        evaluation = feedback_engine.evaluate_answer(question, text)
        body = (
            body_language.analyze_body_language(data.get("body_metrics"))
            if data.get("body_metrics")
            else None
        )

        stored = db.add_answer(session_id, {
            "round_id": round_id,
            "question": question,
            "category": category,
            "difficulty": difficulty,
            "type": "theory",
            "answer": text,
            "transcript": transcript,
            "duration_seconds": round(duration, 1),
            "score": evaluation.get("score", 0),
            "feedback": evaluation,
            "speech": speech,
            "body_language": body,
        })
        return jsonify({
            "answer_id": stored["id"],
            "score": evaluation.get("score"),
            "feedback": evaluation,
            "speech": speech,
            "body_language": body,
        }), 201

    @app.post("/api/sessions/<session_id>/coding")
    def submit_coding(session_id):
        session = db.get_session(session_id)
        if not session:
            return api_error("Session not found", 404)
        if session["status"] == "completed":
            return api_error("Session already completed", 409)

        data = request.get_json(silent=True) or {}
        challenge_id = (data.get("challenge_id") or "").strip()
        code = data.get("code") or ""
        language = data.get("language") or session["coding_language"]
        title = data.get("title") or challenge_id

        result, status = coding_challenges.run_submission(challenge_id, code, language=language)
        if status != 200:
            return jsonify(result), status

        passed = result.get("passed", 0)
        total = result.get("total", 0)
        score_percent = result.get("score_percent", 0)
        score = round(score_percent / 10, 1)

        suggestions = [f"Solution passed {passed} of {total} hidden test cases."]
        if passed < total:
            suggestions.append(
                "Review the failing test cases and check edge cases (empty input, single element, large values)."
            )
        stored = db.add_answer(session_id, {
            "round_id": data.get("round_id") or "technical",
            "question": title,
            "category": "Coding",
            "difficulty": data.get("difficulty") or session["coding_difficulty"],
            "type": "coding",
            "challenge_id": challenge_id,
            "language": language,
            "code": code,
            "passed": passed,
            "total": total,
            "score_percent": score_percent,
            "score": score,
            "feedback": {"source": "runner", "score": score, "suggestions": suggestions},
        })
        return jsonify({
            "answer_id": stored["id"],
            **result,
            "score": score,
        }), 201

    @app.post("/api/sessions/<session_id>/complete")
    def complete_session(session_id):
        session = db.complete_session(session_id)
        if not session:
            return api_error("Session not found", 404)
        result = review.build_review(session["answers"], role=session["role"])
        db.save_review(session_id, result)
        log.info(
            "Session %s completed: overall %.1f/10 (%d answers)",
            session["id"],
            result.get("overall_score", 0),
            len(session.get("answers", [])),
        )
        return jsonify({"session": session, "review": result})

    # ---- static frontend / 404s -----------------------------------------------

    _HTTP_ERRORS = {
        400: "Bad request",
        404: "Not found",
        405: "Method not allowed",
        413: "Upload too large (max 8 MB)",
        415: "Unsupported media type",
        422: "Unprocessable request",
    }

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(413)
    @app.errorhandler(415)
    @app.errorhandler(422)
    def http_error(error):
        return jsonify({"error": _HTTP_ERRORS.get(error.code, "Request failed")}), error.code

    @app.errorhandler(500)
    def internal_error(error):
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return jsonify({"error": "Internal server error"}), 500

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def frontend(path):
        """Serve the built React app in production; fall back to a hint in dev."""
        if path.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            candidate = os.path.join(_FRONTEND_DIST, path)
            if path and os.path.isfile(candidate):
                return send_from_directory(_FRONTEND_DIST, path)
            return send_from_directory(_FRONTEND_DIST, "index.html")
        return jsonify({"error": "Frontend not built", "hint": "Run `npm run dev` in frontend/"}), 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    log.info("=" * 60)
    log.info("Speak2Success API starting")
    log.info("  mode:  %s", "development (debug)" if debug else "production")
    log.info("  port:  %s", port)
    log.info("  AI:    %s", ai_config.status())
    if not ai_config.is_configured():
        log.info("  NOTE:  no GEMINI_API_KEY set - using offline question bank and heuristic feedback")
    storage_dir = os.environ.get("STORAGE_PATH") or os.path.join(_BACKEND_DIR, "data", "speak2success.sqlite3")
    log.info("  db:    %s", storage_dir)
    log.info("  audio: %s", os.environ.get("AUDIO_DIR") or _AUDIO_DIR)
    log.info("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)  # noqa: S104 - dev server bound to all interfaces
