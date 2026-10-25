"""Resume parsing + question generation endpoints."""
from io import BytesIO


def test_resume_parse_txt(client):
    resume = (
        "Alex Doe\nFull Stack Developer with 4 years of experience.\n"
        "Skills: React, Flask, MongoDB, Docker. Led a team project.\n"
    )
    res = client.post(
        "/api/resume/parse",
        data={"file": (BytesIO(resume.encode()), "alex.txt")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["word_count"] > 0
    assert "web" in data["skills"] or "database" in data["skills"]


def test_resume_parse_rejects_unknown_type(client):
    res = client.post(
        "/api/resume/parse",
        data={"file": (BytesIO(b"nope"), "resume.exe")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_questions_generate_offline(client):
    res = client.post(
        "/api/questions/generate",
        json={"role": "Backend Developer", "category": "Technical", "count": 3, "difficulty": "Medium"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["source"] == "offline"
    assert len(data["questions"]) == 3


def test_languages_and_challenges(client):
    langs = client.get("/api/languages").get_json()
    ids = {lang["id"] for lang in langs["languages"]}
    assert "python" in ids

    easy = client.get("/api/challenges?language=python&difficulty=Easy").get_json()
    assert easy["count"] > 0
    assert all(c["difficulty"] == "Easy" for c in easy["challenges"])
    assert all("starter_code" in c for c in easy["challenges"])


def test_challenges_run_python(client):
    res = client.post(
        "/api/challenges/run",
        json={
            "challenge_id": "two-sum",
            "language": "python",
            "code": (
                "def solve(nums, target):\n"
                "    seen = {}\n"
                "    for i, n in enumerate(nums):\n"
                "        if target - n in seen:\n"
                "            return [seen[target - n], i]\n"
                "        seen[n] = i\n"
            ),
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["passed"] == data["total"]
    assert data["passed"] > 0


def test_challenges_run_bad_code(client):
    res = client.post(
        "/api/challenges/run",
        json={
            "challenge_id": "two-sum",
            "language": "python",
            "code": "def solve(nums, target):\n    return 1/0\n",
        },
    )
    assert res.status_code == 200
    assert res.get_json()["passed"] == 0
