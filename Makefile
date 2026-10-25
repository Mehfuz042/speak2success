# Speak2Success developer shortcuts.
# Requires a Python 3.10+ virtualenv at .venv and Node.js 18+ for the frontend.

PYTHON := .venv/Scripts/python.exe
RUF    := .venv/Scripts/ruff.exe

.PHONY: setup backend frontend test test-frontend lint check clean

## Create the venv, install backend deps (frontend needs `npm install` too)
setup:
	python -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r backend/requirements-dev.txt

## Run the Flask dev server on http://localhost:5000
backend:
	$(PYTHON) backend/app.py

## Run the Vite dev server on http://localhost:5173
frontend:
	cd frontend && npm run dev

## Run the backend test suite with coverage
test:
	$(PYTHON) -m pytest

## Test the frontend head-steadiness window logic (Node only, no browser)
test-frontend:
	cd frontend && npm test

## Lint the backend with ruff
lint:
	$(RUF) check backend

## Lint + test
check: lint test test-frontend

## Remove caches and coverage artifacts
clean:
	-$(PYTHON) -m py_cleanup backend 2>NUL || true
	-rmdir /s /q .pytest_cache 2>NUL || true
	-rmdir /s /q .ruff_cache 2>NUL || true
