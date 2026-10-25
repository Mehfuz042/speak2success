"""
AI Configuration Module
------------------------
Speak2Success talks to **Google Gemini** through Gemini's OpenAI-compatible
endpoint (https://generativelanguage.googleapis.com/v1beta/openai/) so a single
OpenAI-compatible client powers question generation, answer feedback and the
final Success Report.

Set in backend/.env (or environment):
    GEMINI_API_KEY   Google Gemini API key (starts with "AIza")
    OPENAI_MODEL     optional model override (default gemini-3.5-flash)
    OPENAI_BASE_URL  optional endpoint override (e.g. real OpenAI)

Everything AI-related falls back to deterministic offline logic when no key
is configured, so the platform works end-to-end without any API.
"""
import logging
import os
import time

try:
    from openai import OpenAI
except ImportError:  # the openai package is optional at runtime
    OpenAI = None

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.5-flash"
# When the primary model is overloaded (HTTP 503) or rate-limited, try these in order.
DEFAULT_FALLBACK_MODELS = ("gemini-3.6-flash",)

log = logging.getLogger("speak2success.ai")

# After every model fails (quota exhausted or a prolonged outage), skip live
# calls briefly so each answer/report falls back immediately instead of paying
# the full timeout on every request. A later request retries automatically.
_AI_COOLDOWN_SECONDS = 120
_last_error = None
_last_error_at = None
_cooldown_until = 0.0


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or GEMINI_BASE_URL).rstrip("/")


def model_name() -> str:
    return os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL


def is_configured() -> bool:
    """True when an API key is present and the client library is installed."""
    return bool(api_key()) and OpenAI is not None


def is_available() -> bool:
    """True when AI is configured and not in a post-failure cooldown."""
    return is_configured() and time.monotonic() >= _cooldown_until


def runtime_status():
    """Live AI status for the health endpoint (no secrets included)."""
    cooldown = max(0, int(round(_cooldown_until - time.monotonic())))
    return {
        "available": is_available(),
        "cooldown_seconds": cooldown,
        "last_error": _last_error,
        "last_error_at": _last_error_at,
    }


def _record_success():
    global _last_error, _last_error_at, _cooldown_until
    _last_error = None
    _last_error_at = None
    _cooldown_until = 0.0


def _record_failure(exc):
    global _last_error, _last_error_at, _cooldown_until
    _last_error = str(exc).splitlines()[0][:300]
    _last_error_at = time.time()
    _cooldown_until = time.monotonic() + _AI_COOLDOWN_SECONDS


def get_client():
    """Return a configured OpenAI-compatible client, or None if unavailable."""
    if not is_configured():
        return None
    # No retries at the SDK level: chat_completion handles model fallbacks and
    # short retries explicitly so a 429/503 cannot block session creation for long.
    return OpenAI(
        api_key=api_key(),
        base_url=base_url(),
        timeout=10.0,
        max_retries=0,
    )


def model_candidates():
    """Primary model first, then configured/default fallbacks (de-duplicated)."""
    configured = [
        m.strip()
        for m in os.environ.get("OPENAI_FALLBACK_MODELS", "").split(",")
        if m.strip()
    ]
    ordered = [model_name(), *configured, *DEFAULT_FALLBACK_MODELS]
    seen = set()
    return [m for m in ordered if not (m in seen or seen.add(m))]


def chat_completion(**kwargs):
    """Call the chat API, falling back to the next model on overload/rate limits.

    Raises the last error when every candidate fails, so callers can fall back to
    their deterministic offline implementation.
    """
    client = get_client()
    if client is None:
        raise RuntimeError("AI client is not configured")
    if time.monotonic() < _cooldown_until:
        raise RuntimeError(_last_error or "AI is temporarily unavailable")

    last_error = None
    for model in model_candidates():
        try:
            response = client.chat.completions.create(model=model, **kwargs)
            _record_success()
            return response
        except Exception as exc:  # noqa: BLE001 - try the next model, then re-raise
            last_error = exc
            log.warning("Gemini call failed for %s: %s", model, exc)
    _record_failure(last_error)
    raise last_error  # type: ignore[misc]


def status() -> str:
    """Human-readable AI status for the health endpoint / startup log."""
    if not is_configured():
        return "offline-heuristics"
    return f"gemini:{model_name()}"
