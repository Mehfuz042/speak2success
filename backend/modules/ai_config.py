"""
AI Configuration Module
------------------------
Speak2Success talks to **Google Gemini** through Gemini's OpenAI-compatible
endpoint (https://generativelanguage.googleapis.com/v1beta/openai/) so a single
OpenAI-compatible client powers question generation, answer feedback and the
final Success Report.

Set in backend/.env (or environment):
    GEMINI_API_KEY   Google Gemini API key (starts with "AIza")
    OPENAI_MODEL     optional model override (default gemini-2.5-flash)
    OPENAI_BASE_URL  optional endpoint override (e.g. real OpenAI)

Everything AI-related falls back to deterministic offline logic when no key
is configured, so the platform works end-to-end without any API.
"""
import os

try:
    from openai import OpenAI
except ImportError:  # the openai package is optional at runtime
    OpenAI = None

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.5-flash"


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or GEMINI_BASE_URL).rstrip("/")


def model_name() -> str:
    return os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL


def is_configured() -> bool:
    """True when an API key is present and the client library is installed."""
    return bool(api_key()) and OpenAI is not None


def get_client():
    """Return a configured OpenAI-compatible client, or None if unavailable."""
    if not is_configured():
        return None
    # No retries: when Gemini is rate-limited (429), fall back to the offline
    # question bank immediately rather than blocking session creation for 10-30s.
    # Individual callers can catch the exception and use offline logic.
    return OpenAI(
        api_key=api_key(),
        base_url=base_url(),
        timeout=10.0,
        max_retries=0,
    )


def status() -> str:
    """Human-readable AI status for the health endpoint / startup log."""
    if not is_configured():
        return "offline-heuristics"
    return f"gemini:{model_name()}"
