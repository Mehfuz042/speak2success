# ---- Stage 1: build the React frontend -------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Stage 2: Python runtime with the Flask backend + built frontend -------
FROM python:3.10-slim AS backend
WORKDIR /app

# MediaPipe / OpenCV runtime libraries, plus Node for the JS coding runner.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libglib2.0-0 \
        libstdc++6 \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements-prod.txt backend/requirements-prod.txt
RUN pip install --no-cache-dir -r backend/requirements-prod.txt

COPY backend/ backend/
COPY --from=frontend /build/dist/ frontend/dist/

ENV PORT=5000 \
    ALLOWED_ORIGINS=http://localhost:5000 \
    STORAGE_PATH=/app/backend/data/speak2success.sqlite3 \
    AUDIO_DIR=/app/backend/data/audio \
    FLASK_DEBUG=0

WORKDIR /app/backend

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3).status==200 else 1)" || exit 1

# gunicorn with the gevent-websocket worker (flask-sock compatible) so both
# the REST API and the real-time /ws/coach stream run under one production server.
CMD ["gunicorn", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", \
     "-w", "1", "--worker-connections", "1000", "--timeout", "120", \
     "--bind", "0.0.0.0:5000", "app:app"]
