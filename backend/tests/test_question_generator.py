"""Offline question generator: variety and recency avoidance."""
from modules.question_generator import _RECENT, _offline_generate, generate_language_theory


def test_offline_generate_is_varied_across_calls():
    _RECENT.clear()
    seen = {
        _offline_generate("DevOps Engineer", ["docker"], "Medium", "Technical", 1)[0]["question"]
        for _ in range(4)
    }
    assert len(seen) >= 2


def test_recency_avoids_immediate_repeats():
    _RECENT.clear()
    first = _offline_generate("DevOps Engineer", ["docker"], "Medium", "Managerial", 1)[0]["question"]
    second = _offline_generate("DevOps Engineer", ["docker"], "Medium", "Managerial", 1)[0]["question"]
    assert first != second


def test_language_theory_is_varied():
    _RECENT.clear()
    seen = {generate_language_theory("python", "Medium", 1)[0]["question"] for _ in range(4)}
    assert len(seen) >= 2


def test_language_theory_avoids_immediate_repeats():
    _RECENT.clear()
    first = generate_language_theory("python", "Medium", 1)[0]["question"]
    second = generate_language_theory("python", "Medium", 1)[0]["question"]
    assert first != second
