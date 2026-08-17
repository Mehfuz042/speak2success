# Speak2Success 🎤 — Speak Better. Perform Better.

An AI-powered **professional mock interview platform**. Upload your resume, pick your
target role, and an AI interviewer (Google Gemini) runs you through three real interview
rounds — **Managerial → Technical (theory + live coding) → HR** — then hands you a
full **Success Report** with scores, strengths, weaknesses and next steps.

## Interview flow

```
Resume upload → Role & coding setup → Managerial Round → Technical Round
                                        (theory + language questions + coding problems
                                         with hidden test cases on Python/JS/Java/C++) → HR Round
→ Success Report (overall score, category breakdown, strengths, weaknesses, action plan)
```

- **Three professional rounds** — Managerial (leadership/conflict), Technical
  (role theory + coding-language theory + coding problems at Easy/Medium/Hard), HR
  (motivation/culture fit).
- **Choose your coding language** (Python, JavaScript, Java, C++) and difficulty; the
  Technical round generates coding problems with starter code and runs them against
  **hidden test cases** in an isolated subprocess (Python is bundled; JS needs Node;
  Java needs a JDK; C++ needs g++).
- **Speech-to-text** via the browser's Web Speech API (type as a fallback), with per-answer
  speech analysis (WPM, filler words, clarity) and STAR-aware answer feedback.
- **Real-time body-language coach** — MediaPipe (in the backend, over WebSockets) tracks
  your eye contact, smile, blink rate, head stability and posture (slouching / leaning /
  sitting too close) live during every answer, feeds per-answer scores back, and folds a
  body-language summary into the Success Report.
- **Answer audio recording** — record and keep each spoken answer so you can replay it
  while reviewing your report.
- **Persistent history** — every session is saved to SQLite and survives restarts; the
  **Past interviews** page lists old reports with scores, reopens any Success Report, and
  lets you delete entries.
- **Gemini-powered** question generation and answer feedback when a key is set; a fully
  offline question bank + heuristic coach keeps everything working without one.
- **Live webcam panel** — mirrored preview, mic-level meter, camera/mic toggles.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite 5, Tailwind CSS 3 |
| Backend | Python 3.10, Flask 3 |
| AI (optional) | Google Gemini via its OpenAI-compatible endpoint (`gemini-3.5-flash`, overridable) |
| Computer vision | MediaPipe (Pose + Face Mesh) on the backend, frames streamed over WebSockets |
| Coding runner | Subprocess-isolated Python/Node/Java/C++ with hard timeouts |
| Speech | Web Speech API (browser) + WPM/filler/clarity analysis |
| Persistence | SQLite via stdlib `sqlite3` (`STORAGE_PATH`), audio files on disk |

## Getting started

Prerequisites: **Python 3.10+** and **Node.js 18+**.

```powershell
# 1. Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt

# 2. Frontend
cd frontend
npm install
cd ..

# 3. Run both dev servers (two terminals)
make backend          # Flask API on :5000  (or: python backend\app.py)
make frontend         # Vite dev server on :5173  (or: cd frontend && npm run dev)
```

Open **http://localhost:5173** (dev) — or just **http://localhost:5000** once built
(`npm run build` in `frontend/`), which serves the whole app from one process.

### Docker (recommended for deployment)

```powershell
docker compose up --build -d     # builds frontend + backend, serves on :5000
docker compose logs -f app       # follow logs
```

The image is self-contained (Flask serves the built React app), persists sessions
under `./backend/data` via a volume, and pre-installs Node so Python and JavaScript
coding challenges run inside the container. Java/C++ challenges are skipped unless you
add a JDK / `g++` to the image.

The container runs **gunicorn** (gevent-websocket worker) so the REST API and the
real-time `/ws/coach` stream share one production server; the Flask dev server is
only used when running `python backend/app.py` locally.

## Configuration

Copy `backend/.env.example` to `backend/.env`:

```ini
PORT=5000
ALLOWED_ORIGINS=http://localhost:5173
GEMINI_API_KEY=AIza...   # optional: enables AI questions + feedback
OPENAI_MODEL=gemini-3.5-flash   # optional model override
STORAGE_PATH=backend/data/speak2success.sqlite3   # omit for an in-memory store
# AUDIO_DIR=backend/data/audio                    # where recorded answers are kept
```

`GEMINI_API_KEY` can be a free-tier Google AI Studio key. When set, question
generation, answer feedback and the final report use Gemini; without it everything runs
on the offline engine (with randomized, non-repeating questions). `backend/.env` is
git-ignored. The test suite forces the offline engine so it never depends on the live API.

## Project structure

```
.
├─ backend/
│  ├─ app.py                 # Flask app factory + full REST API
│  ├─ requirements*.txt
│  ├─ .env(.example)
│  ├─ modules/
│  │  ├─ ai_config.py        # Gemini client wiring (OpenAI-compatible)
│  │  ├─ resume_parser.py    # PDF/TXT → skills, roles, experience
│  │  ├─ question_generator.py   # MR/TR/HR + language theory (Gemini + offline bank)
│  │  ├─ coding_challenges.py    # 13-challenge bank + multi-language runner
│  │  ├─ speech_analyzer.py      # WPM, fillers, clarity
│  │  ├─ body_language.py        # MediaPipe frame analysis + posture/engagement scoring
│  │  ├─ feedback_engine.py      # answer scoring (Gemini or STAR heuristics)
│  │  ├─ review.py               # Success Report
│  │  └─ storage.py              # SQLite session store (answers, audio refs)
│  └─ tests/                 # pytest suite (resume, questions, coding, body-language, audio, persistence, full flow)
├─ frontend/
│  ├─ index.html, vite.config.js, tailwind.config.js
│  └─ src/
│     ├─ App.jsx             # hash routing: Home / Setup / Interview / Review / History / Report
│     ├─ api/client.js       # fetch wrapper for every endpoint
│     ├─ hooks/              # useMediaDevices, useSpeechRecognition, useBodyCoach
│     ├─ components/CodingEditor.jsx
│     └─ views/              # Home, Setup, InterviewRoom, Review, History
├─ Dockerfile                # multi-stage: Vite build → Python runtime
├─ docker-compose.yml        # single-service deploy on :5000
├─ pyproject.toml            # pytest + ruff config
└─ Makefile
```

## API reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status, AI provider, Gemini key presence |
| POST | `/api/resume/parse` | Upload PDF/TXT → skills, suggested roles, experience |
| GET | `/api/languages` | Supported coding languages |
| GET | `/api/challenges?language=&difficulty=` | Coding challenges + starter code |
| POST | `/api/challenges/run` | Run code against hidden test cases |
| POST | `/api/questions/generate` | Generate questions for a round/category |
| POST | `/api/feedback/evaluate` | Score a single answer |
| POST | `/api/speech/analyze` | WPM / fillers / clarity from transcript + duration |
| POST | `/api/body-language/analyze` | Analyze a single base64 JPEG frame (face, gaze, posture) |
| POST | `/api/body-language/score` | Score an aggregated per-answer body-metrics dict |
| WS | `/ws/coach` | Stream webcam frames → live posture/engagement metrics |
| POST | `/api/sessions` | Create a session (3 rounds, coding config) |
| GET | `/api/sessions` | List past sessions (with overall score when completed) |
| GET | `/api/sessions/<id>` | Session + answers (+ review when completed) |
| DELETE | `/api/sessions/<id>` | Delete a session and its recorded audio |
| POST | `/api/sessions/<id>/answers` | Submit a spoken/typed answer |
| POST | `/api/sessions/<id>/coding` | Submit a coding solution (runs hidden tests) |
| POST | `/api/sessions/<id>/answers/<aid>/audio` | Upload a recorded answer (multipart `audio`) |
| GET | `/api/sessions/<id>/answers/<aid>/audio` | Stream a recorded answer back |
| POST | `/api/sessions/<id>/complete` | Finish and build the Success Report |

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest    # backend tests (resume, coding runner, full flow)
.\.venv\Scripts\ruff.exe check backend  # lint
make check
```

## Security notes

- The coding runner executes submissions in a subprocess with a hard timeout but is
  **not a true sandbox** — don't expose `/api/challenges/run` to untrusted public traffic
  without containerizing it (see `backend/modules/coding_challenges.py`).
- The body-language pipeline sends **downscaled JPEG frames** (max 320px) over a WebSocket;
  frames are processed and discarded — raw video is never stored or logged.
- `backend/.env` is git-ignored; never commit real API keys.
- Camera frames never leave the browser for storage; only posture metrics and transcribed text go to the API.

## License

MIT.
