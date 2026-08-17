"""Full mock-interview session flow: three rounds + coding + review."""
from conftest import _create_session


def _answer_payload(question, category="Technical", round_id="technical"):
    return {
        "round_id": round_id,
        "question": question,
        "category": category,
        "difficulty": "Medium",
        "answer": (
            "In my last role I had to ship a payments feature. I led a small team, "
            "designed the API and implemented the integration. As a result, rollout "
            "time dropped by 40 percent."
        ),
        "transcript": "In my last role I had to ship a payments feature. I led the team.",
        "duration_seconds": 20,
    }


def test_full_interview_flow(client):
    res = _create_session(client)
    assert res.status_code == 201
    session = res.get_json()["session"]

    assert len(session["rounds"]) == 3
    ids = [r["id"] for r in session["rounds"]]
    assert ids == ["managerial", "technical", "hr"]

    mr = next(r for r in session["rounds"] if r["id"] == "managerial")
    tr = next(r for r in session["rounds"] if r["id"] == "technical")
    hr = next(r for r in session["rounds"] if r["id"] == "hr")
    assert all(q["type"] == "theory" for q in mr["questions"])
    assert any(q["type"] == "coding" for q in tr["questions"])
    assert any(q["type"] == "theory" and q.get("language") == "python" for q in tr["questions"])

    coding = next(q for q in tr["questions"] if q["type"] == "coding")
    for q in tr["questions"]:
        if q["type"] != "coding":
            payload = _answer_payload(q["question"], "Technical", "technical")
            ans = client.post(f"/api/sessions/{session['id']}/answers", json=payload)
            assert ans.status_code == 201
            assert 1 <= ans.get_json()["score"] <= 10

    code = client.post(
        f"/api/sessions/{session['id']}/coding",
        json={
            "challenge_id": coding["challenge_id"],
            "language": "python",
            "title": coding["title"],
            "difficulty": coding["difficulty"],
            "round_id": "technical",
            "code": (
                "def solve(nums, target):\n"
                "    for i in range(len(nums)):\n"
                "        for j in range(i+1, len(nums)):\n"
                "            if nums[i] + nums[j] == target:\n"
                "                return [i, j]\n"
            ),
        },
    )
    assert code.status_code == 201
    assert code.get_json()["passed"] == code.get_json()["total"]

    for q in list(mr["questions"]) + list(hr["questions"]):
        payload = _answer_payload(q["question"], q["category"], q["category"].lower())
        ans = client.post(f"/api/sessions/{session['id']}/answers", json=payload)
        assert ans.status_code == 201

    complete = client.post(f"/api/sessions/{session['id']}/complete")
    assert complete.status_code == 200
    review_data = complete.get_json()["review"]
    assert "overall_score" in review_data
    assert "Coding" in review_data["category_breakdown"]
    assert review_data["category_breakdown"]["Coding"] >= 9.0

    got = client.get(f"/api/sessions/{session['id']}")
    assert got.get_json()["session"]["status"] == "completed"


def test_submit_answer_requires_text(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    res = client.post(
        f"/api/sessions/{session['id']}/answers",
        json={"question": "Tell me about yourself", "answer": ""},
    )
    assert res.status_code == 400
