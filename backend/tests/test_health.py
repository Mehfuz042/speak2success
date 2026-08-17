"""API smoke tests."""


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "speak2success"
    assert data["ai_provider"] == "gemini"


def test_health_reports_ai_offline_in_tests(client):
    """The test suite must never depend on a live Gemini key."""
    res = client.get("/api/health")
    assert res.get_json()["gemini_configured"] is False
    assert res.get_json()["ai"] == "offline-heuristics"


def test_unknown_api_route_returns_json_404(client):
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Not found"
