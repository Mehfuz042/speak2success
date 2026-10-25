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

# Node is required for the JavaScript coding runner. The glib/gomp libraries are
# only needed if you opt into the optional server-side vision stack
# (backend/requirements-vision.txt); the web app runs MediaPipe in the browser.
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
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','5000'); sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+p+'/api/health', timeout=3).status==200 else 1)" || exit 1

# gunicorn with the gevent-websocket worker (flask-sock compatible) so both
# the REST API and the real-time /ws/coach stream run under one production server.
# Bind $PORT at runtime: Render (and most PaaS hosts) injects PORT and routes to it.
CMD ["sh", "-c", "gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 --worker-connections 1000 --timeout 120 --bind 0.0.0.0:${PORT:-5000} app:app"]
