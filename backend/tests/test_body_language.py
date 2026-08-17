"""Body-language module + API coverage (Phase 3: posture / engagement)."""
import base64

import cv2
import numpy as np
import pytest
from conftest import _create_session

from modules.body_language import (
    aggregate_frames,
    analyze_body_language,
    analyze_frame,
)


def _blank_jpeg():
    img = np.zeros((480, 640, 3), np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _fake_frames(n=10, **overrides):
    base = {
        "frame_ok": True,
        "ts_ms": 0,
        "face_present": True,
        "eye_contact": True,
        "eye_contact_pct": 90.0,
        "smiling": True,
        "blink": False,
        "head_steady": True,
        "pose_present": True,
        "posture": "good",
        "shoulder_angle": 2.0,
        "confidence": 96.0,  # matches analyze_frame's fused confidence for these cues
    }
    base.update(overrides)
    return [{**base, "ts_ms": 1000 + i * 200} for i in range(n)]


def test_analyze_frame_blank_jpeg():
    metrics = analyze_frame(_blank_jpeg())
    assert metrics["frame_ok"] is True
    assert metrics["face_present"] is False
    assert metrics["pose_present"] is False
    assert metrics["posture"] == "unknown"


def test_analyze_frame_invalid_bytes():
    metrics = analyze_frame(b"not-a-jpeg")
    assert metrics["frame_ok"] is False
    assert metrics["errors"]


def test_aggregate_and_score_good_metrics():
    agg = aggregate_frames(_fake_frames())
    assert agg["eye_contact_pct"] == pytest.approx(90.0)
    assert agg["face_present_pct"] == 100.0
    assert agg["smile_pct"] == 100.0
    assert agg["duration_seconds"] == pytest.approx(1.8)
    result = analyze_body_language(agg)
    assert 1.0 <= result["score"] <= 10.0
    assert result["metrics"]["eye_contact_pct"] == pytest.approx(90.0)


def test_aggregate_counts_blinks_and_shifts():
    frames = _fake_frames()
    frames[2]["blink"] = True
    frames[3]["blink"] = True
    frames[4]["posture"] = "slouching"
    frames[5]["posture"] = "leaning_left"
    agg = aggregate_frames(frames)
    assert agg["posture_shift_count"] >= 1
    assert "slouching" in agg["posture_breakdown"]
    assert agg["blink_rate_per_min"] is not None


def test_score_penalizes_no_face_and_poor_posture():
    no_camera = analyze_body_language({})
    assert no_camera["score"] < 7.0
    bad = aggregate_frames(_fake_frames(face_present=False, eye_contact=False, eye_contact_pct=10.0))
    scored = analyze_body_language(bad)
    assert scored["score"] < no_camera["score"]
    slouch = aggregate_frames(
        _fake_frames(eye_contact=False, eye_contact_pct=10.0, posture="slouching")
    )
    assert analyze_body_language(slouch)["score"] < 7.0


def test_empty_aggregate():
    assert aggregate_frames([]) == {}


def test_frame_confidence_key_present():
    metrics = analyze_frame(_blank_jpeg())
    assert "confidence" in metrics
    assert metrics["confidence"] == 0.0  # no face visible


def test_aggregate_confidence_good_frames():
    agg = aggregate_frames(_fake_frames())
    # eye 90*0.4 + head 0.2 + posture 0.2 + smile 0.2 => 0.96 -> 96.0
    assert agg["confidence_pct"] == pytest.approx(96.0)


def test_aggregate_confidence_none_without_face():
    agg = aggregate_frames(_fake_frames(face_present=False))
    assert agg["confidence_pct"] is None


def test_score_includes_confidence():
    result = analyze_body_language(aggregate_frames(_fake_frames()))
    conf = result["confidence"]
    assert conf["score"] is not None
    assert conf["pct"] == pytest.approx(96.0)
    assert conf["level"] == "Confident"
    assert result["metrics"]["confidence_pct"] == pytest.approx(96.0)


def test_confidence_flags_nervous_cues():
    agg = aggregate_frames(
        _fake_frames(
            eye_contact=False,
            eye_contact_pct=10.0,
            posture="slouching",
            smiling=False,
            confidence=12.0,
        )
    )
    conf = analyze_body_language(agg)["confidence"]
    assert conf["score"] < 6.0
    assert conf["level"] == "Nervous"


def test_confidence_no_camera_data():
    conf = analyze_body_language({})["confidence"]
    assert conf["score"] is None
    assert conf["level"] == "No camera data"


# ---- API ------------------------------------------------------------------


def test_body_language_analyze_endpoint(client):
    jpeg = _blank_jpeg()
    res = client.post(
        "/api/body-language/analyze",
        json={"frame": base64.b64encode(jpeg).decode(), "ts_ms": 42},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["frame_ok"] is True
    assert body["face_present"] is False


def test_body_language_analyze_bad_payload(client):
    assert client.post("/api/body-language/analyze", json={}).status_code == 400
    assert client.post("/api/body-language/analyze", json={"frame": "%%%notbase64%%%"}).status_code == 400


def test_body_language_score_endpoint(client):
    res = client.post(
        "/api/body-language/score",
        json=aggregate_frames(_fake_frames()),
    )
    assert res.status_code == 200
    assert "score" in res.get_json()


def test_submit_answer_with_body_metrics(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    res = client.post(
        f"/api/sessions/{session['id']}/answers",
        json={
            "round_id": "managerial",
            "question": "Tell me about yourself",
            "category": "Managerial",
            "difficulty": "Medium",
            "answer": "I led a team and shipped a feature on time.",
            "transcript": "I led a team and shipped a feature.",
            "duration_seconds": 15,
            "body_metrics": aggregate_frames(_fake_frames()),
        },
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["body_language"]["score"] is not None
    assert body["body_language"]["source"] == "heuristic"


def test_review_includes_body_language(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    client.post(
        f"/api/sessions/{session['id']}/answers",
        json={
            "round_id": "managerial",
            "question": "Tell me about yourself",
            "category": "Managerial",
            "answer": "I led a team and shipped a feature on time.",
            "duration_seconds": 15,
            "body_metrics": aggregate_frames(_fake_frames()),
        },
    )
    complete = client.post(f"/api/sessions/{session['id']}/complete")
    review_data = complete.get_json()["review"]
    body = review_data["body_language"]
    assert body is not None
    assert body["covered_answers"] == 1
    assert body["metrics"]["eye_contact_pct"] is not None
    assert body["confidence"] is not None
    assert body["confidence"]["score"] is not None
    assert body["confidence"]["level"] in ("Confident", "Composed", "Nervous")
