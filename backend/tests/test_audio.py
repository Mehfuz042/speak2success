"""Answer audio upload + playback coverage."""
import io
import os
import tempfile

from conftest import _create_session

os.environ.setdefault("AUDIO_DIR", tempfile.mkdtemp(prefix="s2s-test-audio-"))


def _answer_id(client, session_id):
    res = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "question": "Tell me about yourself",
            "category": "Managerial",
            "answer": "I led a team and shipped a feature on time.",
        },
    )
    assert res.status_code == 201
    return res.get_json()["answer_id"]


def test_audio_upload_and_download(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    answer_id = _answer_id(client, session["id"])

    upload = client.post(
        f"/api/sessions/{session['id']}/answers/{answer_id}/audio",
        data={"audio": (io.BytesIO(b"fake-webm-bytes"), "answer.webm", "audio/webm")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    assert upload.get_json()["audio_file"].startswith(answer_id)

    download = client.get(f"/api/sessions/{session['id']}/answers/{answer_id}/audio")
    assert download.status_code == 200
    assert download.data == b"fake-webm-bytes"


def test_audio_requires_existing_answer(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    upload = client.post(
        f"/api/sessions/{session['id']}/answers/nonexistent/audio",
        data={"audio": (io.BytesIO(b"x"), "a.webm", "audio/webm")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 404


def test_review_flags_has_audio(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    answer_id = _answer_id(client, session["id"])
    client.post(
        f"/api/sessions/{session['id']}/answers/{answer_id}/audio",
        data={"audio": (io.BytesIO(b"webm"), "a.webm", "audio/webm")},
        content_type="multipart/form-data",
    )
    client.post(f"/api/sessions/{session['id']}/complete")
    review = client.get(f"/api/sessions/{session['id']}").get_json()["review"]
    row = next(a for a in review["answer_feedback"] if a["answer_id"] == answer_id)
    assert row["has_audio"] is True


def test_no_audio_for_missing_recording(client):
    res = _create_session(client)
    session = res.get_json()["session"]
    answer_id = _answer_id(client, session["id"])
    assert (
        client.get(f"/api/sessions/{session['id']}/answers/{answer_id}/audio").status_code
        == 404
    )
