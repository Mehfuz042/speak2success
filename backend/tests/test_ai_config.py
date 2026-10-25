"""AI configuration: model ordering and overload fallback."""
from types import SimpleNamespace

import pytest

from modules import ai_config


@pytest.fixture(autouse=True)
def _reset_ai_runtime_state():
    ai_config._record_success()
    yield
    ai_config._record_success()


def test_model_candidates_primary_then_fallbacks_without_duplicates(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "primary-model")
    monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "fallback-a, primary-model, fallback-b")
    candidates = ai_config.model_candidates()
    assert candidates[:3] == ["primary-model", "fallback-a", "fallback-b"]
    assert len(candidates) == len(set(candidates))


def _fake_client(create):
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )


def test_chat_completion_falls_back_when_primary_is_overloaded(monkeypatch):
    calls = []

    def create(model, **_kwargs):
        calls.append(model)
        if model == "overloaded":
            raise RuntimeError("503 service unavailable")
        return {"model": model, "ok": True}

    monkeypatch.setattr(ai_config, "get_client", lambda: _fake_client(create))
    monkeypatch.setenv("OPENAI_MODEL", "overloaded")
    monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "healthy")
    monkeypatch.setattr(ai_config, "DEFAULT_FALLBACK_MODELS", ())

    result = ai_config.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert result == {"model": "healthy", "ok": True}
    assert calls == ["overloaded", "healthy"]


def test_chat_completion_raises_when_all_models_fail(monkeypatch):
    def create(model, **_kwargs):
        raise RuntimeError(f"{model} unavailable")

    monkeypatch.setattr(ai_config, "get_client", lambda: _fake_client(create))
    monkeypatch.setenv("OPENAI_MODEL", "first")
    monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "second")
    monkeypatch.setattr(ai_config, "DEFAULT_FALLBACK_MODELS", ())

    with pytest.raises(RuntimeError, match="second unavailable"):
        ai_config.chat_completion(messages=[])

    assert ai_config.runtime_status()["cooldown_seconds"] > 0
    assert ai_config.runtime_status()["last_error"] == "second unavailable"
    with pytest.raises(RuntimeError, match="second unavailable"):
        ai_config.chat_completion(messages=[])
