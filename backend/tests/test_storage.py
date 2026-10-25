"""Persistence layer: SQLite storage + session list/delete API."""
from conftest import _create_session

from modules.storage import Storage


def test_storage_in_memory_round_trip():
    db = Storage()
    s = db.create_session("u", "Full Stack Developer", name="Alex", skills=["react"])
    assert s["status"] == "in_progress"
    ans = db.add_answer(s["id"], {"question": "Tell me about yourself", "score": 8})
    assert ans["id"]
    completed = db.complete_session(s["id"])
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None
    got = db.get_session(s["id"])
    assert len(got["answers"]) == 1
    assert got["answers"][0]["score"] == 8
    assert got["skills"] == ["react"]
    db.close()


def test_storage_file_persistence_survives_reopen(tmp_path):
    path = str(tmp_path / "store.sqlite3")
    db = Storage(path)
    s = db.create_session("u", "Role", name="A")
    db.add_answer(s["id"], {"question": "Q", "score": 9})
    db.complete_session(s["id"])
    db.close()

    db2 = Storage(path)
    got = db2.get_session(s["id"])
    assert got["status"] == "completed"
    assert got["answers"][0]["question"] == "Q"
    assert got["name"] == "A"
    db2.close()


def test_storage_delete_and_list():
    db = Storage()
    a = db.create_session("u", "Role A")
    b = db.create_session("u", "Role B")
    ids = [s["id"] for s in db.list_sessions()]
    assert a["id"] in ids and b["id"] in ids
    assert db.delete_session(a["id"]) is True
    assert db.delete_session(a["id"]) is False
    assert db.get_session(a["id"]) is None
    assert all(s["id"] != a["id"] for s in db.list_sessions())
    db.close()


def test_list_and_delete_endpoints(client):
    res = _create_session(client)
    sid = res.get_json()["session"]["id"]

    listing = client.get("/api/sessions")
    assert listing.status_code == 200
    sessions = listing.get_json()["sessions"]
    assert any(s["id"] == sid and s["status"] == "in_progress" for s in sessions)

    assert client.delete(f"/api/sessions/{sid}").status_code == 200
    assert client.delete(f"/api/sessions/{sid}").status_code == 404
    listing2 = client.get("/api/sessions").get_json()["sessions"]
    assert not any(s["id"] == sid for s in listing2)


def test_list_reports_overall_score_for_completed(client):
    res = _create_session(client)
    sid = res.get_json()["session"]["id"]
    client.post(
        f"/api/sessions/{sid}/answers",
        json={"question": "Tell me about yourself", "category": "Managerial",
              "answer": "I led a team and shipped a feature on time."},
    )
    client.post(f"/api/sessions/{sid}/complete")
    listing = client.get("/api/sessions").get_json()["sessions"]
    entry = next(s for s in listing if s["id"] == sid)
    assert entry["status"] == "completed"
    assert 0 <= entry["overall_score"] <= 10
