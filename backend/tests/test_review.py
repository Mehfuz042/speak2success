"""Success Report contract: every question, plus body language & confidence."""
from conftest import _create_session

from modules.body_language import aggregate_frames

COUNTS = {
    "managerial_count": 1,
    "technical_count": 1,
    "language_count": 1,
    "coding_count": 1,
    "hr_count": 1,
}


def _fake_body_metrics(**overrides):
    frame = {
        "frame_ok": True,
        "face_present": True,
        "eye_contact": True,
        "eye_contact_pct": 82.0,
        "smiling": True,
        "blink": False,
        "head_steady": True,
        "pose_present": True,
        "posture": "good",
        "confidence": 91.0,
    }
    frame.update(overrides)
    return aggregate_frames([{**frame, "ts_ms": 1000 + i * 200} for i in range(10)])


def _answer(client, session_id, question, category="Technical", round_id="technical", body=None):
    return client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "round_id": round_id,
            "question": question,
            "category": category,
            "difficulty": "Medium",
            "answer": (
                "In my last role I had to ship a payments feature. First I analysed the "
                "bottlenecks, then I led a small team and implemented the API. As a result "
                "rollout time dropped by 40 percent and we shipped two weeks early."
            ),
            "transcript": "In my last role I had to ship a payments feature and led a small team.",
            "duration_seconds": 40,
            "body_metrics": body if body is not None else _fake_body_metrics(),
        },
    )


def test_report_covers_every_question_even_when_skipped(client):
    res = _create_session(client, **COUNTS)
    session = res.get_json()["session"]

    managerial = next(r for r in session["rounds"] if r["id"] == "managerial")["questions"][0]
    hr = next(r for r in session["rounds"] if r["id"] == "hr")["questions"][0]
    assert _answer(client, session["id"], managerial["question"], "Managerial", "managerial").status_code == 201
    assert _answer(client, session["id"], hr["question"], "HR", "hr").status_code == 201

    review = client.post(f"/api/sessions/{session['id']}/complete").get_json()["review"]

    total_questions = sum(len(r["questions"]) for r in session["rounds"])
    assert review["review_version"] >= 2
    assert review["questions_total"] == total_questions
    assert review["questions_answered"] == 2
    assert review["questions_skipped"] == total_questions - 2
    assert len(review["answer_feedback"]) == total_questions

    answered = [row for row in review["answer_feedback"] if row["answered"]]
    skipped = [row for row in review["answer_feedback"] if not row["answered"]]
    assert len(answered) == 2
    assert len(skipped) == total_questions - 2
    assert all(row["verdict"] == "Not answered" for row in skipped)
    assert all(row["score"] is None for row in skipped)
    assert all(row["improvements"] for row in skipped)


def test_each_answered_question_has_body_language_and_confidence(client):
    res = _create_session(client, **COUNTS)
    session = res.get_json()["session"]
    question = next(r for r in session["rounds"] if r["id"] == "managerial")["questions"][0]
    _answer(client, session["id"], question["question"], "Managerial", "managerial")

    review = client.post(f"/api/sessions/{session['id']}/complete").get_json()["review"]
    row = next(r for r in review["answer_feedback"] if r["answered"])

    # Per-question answer feedback
    assert row["score"] is not None
    assert row["strengths"]
    assert row["improvements"]
    assert row["speech"]["words_per_minute"] is not None

    # Per-question body language + confidence
    body = row["body_language"]
    assert body is not None
    assert body["score"] is not None
    assert row["confidence"]["score"] is not None
    assert row["confidence"]["pct"] is not None
    assert row["confidence"]["level"] in ("Confident", "Composed", "Nervous")
    assert body["metrics"]["eye_contact_pct"] is not None
    assert body["suggestions"]

    # Session-level summary keeps working
    assert review["body_language"]["confidence"]["score"] is not None
    assert review["confidence"]["level"] in ("Confident", "Composed", "Nervous")
    assert review["body_language"]["confidence"]["answers_assessed"] == 1


def test_confidence_is_not_assessed_without_camera(client):
    res = _create_session(client, **COUNTS)
    session = res.get_json()["session"]
    question = next(r for r in session["rounds"] if r["id"] == "hr")["questions"][0]
    _answer(client, session["id"], question["question"], "HR", "hr", body={})

    review = client.post(f"/api/sessions/{session['id']}/complete").get_json()["review"]
    row = next(r for r in review["answer_feedback"] if r["answered"])
    assert row["body_language"] is None
    assert row["confidence"] is None
    assert review["body_language"] is None
