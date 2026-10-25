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
- **Real-time body-language coach** — **MediaPipe Tasks Vision runs fully on-device
  in the browser** (no video leaves the machine) and tracks your eye contact, smile, blink
  rate, head stability and posture (slouching / leaning / sitting too close) live during
  every answer. It shows a live **confidence meter**, feeds per-answer scores back, and
  folds a confidence + body-language summary into the Success Report.
- **Per-question Success Report** — every question is reviewed, in order, including ones
  you skipped: answer score, strengths, improvements, speech pace/clarity, body language,
  confidence level and (for coding) hidden-test results.
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
| Computer vision | **MediaPipe Tasks Vision in the browser** (`@mediapipe/tasks-vision`); no server-side OpenCV/MediaPipe required |
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
$env:STORAGE_PATH="$PWD\backend\data\speak2success.sqlite3"   # persist history
make backend          # Flask API on :5000  (or: python backend\app.py)
make frontend         # Vite dev server on :5173  (or: cd frontend && npm run dev)
```

Without `STORAGE_PATH` the API keeps sessions in memory (fine for a quick demo, but
history is lost when the process restarts). Set it to a file path to persist, or use
Docker, which sets it for you.

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

### Deploy to Render

Render can build the included `Dockerfile` directly; no separate frontend service is needed.

1. Push this project to GitHub (the Dockerfile must stay at the repo root).
2. In Render: **New → Web Service**, connect the repo, and choose **Docker** as the runtime
   (Dockerfile path `./Dockerfile`). Select a region and plan.
3. Set **Health Check Path** to `/api/health`.
4. Add these environment variables (Render injects `PORT` itself — do **not** set it):

   | Key | Value |
   | --- | --- |
   | `STORAGE_PATH` | `/app/backend/data/speak2success.sqlite3` |
   | `AUDIO_DIR` | `/app/backend/data/audio` |
   | `FLASK_DEBUG` | `0` |
   | `ALLOWED_ORIGINS` | `https://<your-service>.onrender.com` |
   | `GEMINI_API_KEY` | optional; free key from Google AI Studio |

5. **Create Web Service** and wait for the health check to pass. Open
   `https://<your-service>.onrender.com/api/health` — it should return
   `"status": "ok"` and `"vision": {"mode": "browser"}`.
6. For durable history, attach a **persistent disk** mounted at `/app/backend/data`.
   Without a disk the filesystem is ephemeral: session history and reports disappear on
   the next deploy or restart (free instances also sleep after idle).

The webcam pipeline needs HTTPS, which Render provides by default. Java/C++ coding
challenges still require adding a JDK / `g++` to the image; Python and JavaScript run
inside the container.

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
| POST | `/api/body-language/analyze` | Optional server-side frame analysis (returns 503 when the optional vision stack is not installed) |
| POST | `/api/body-language/score` | Score an aggregated per-answer body-metrics dict |
| WS | `/ws/coach` | Optional server-side vision stream (degrades cleanly; the web app analyses frames on-device) |
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
cd frontend; npm test                   # head-steadiness window logic (no browser needed)
make check
```

## Security notes

- The coding runner executes submissions in a subprocess with a hard timeout but is
  **not a true sandbox** — don't expose `/api/challenges/run` to untrusted public traffic
  without containerizing it (see `backend/modules/coding_challenges.py`).
- The body-language pipeline runs **entirely in the browser** with MediaPipe Tasks
  Vision; webcam frames are never uploaded, stored or logged. Only the aggregated
  per-answer metrics (percentages/score) are sent to the API with the answer.
- An optional server-side vision stack exists for non-browser clients; install
  `backend/requirements-vision.txt` to enable `/api/body-language/analyze` and
  `/ws/coach`. Without it those endpoints return a clean 503 while the web app keeps
  working normally.
- `backend/.env` is git-ignored; never commit real API keys.
- Camera frames never leave the browser; only posture/confidence metrics and transcribed
  text go to the API.

## License

MIT.
