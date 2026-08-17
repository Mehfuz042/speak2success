"""Job-role support: the /api/roles catalog and role-aware question generation."""
from modules.job_roles import (ROLE_PROFILES, ROLE_TECHNICAL_TOPICS,
                               ROLE_INTERVIEW_QUESTIONS, role_names)


def test_roles_endpoint_lists_all_supported_roles(client):
    res = client.get("/api/roles")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 15
    assert len(data["roles"]) == data["count"]
    assert len(data["roles"]) == len(set(data["roles"]))  # no duplicates


def test_every_role_has_technical_topics_and_skills():
    for profile in ROLE_PROFILES:
        assert profile["role"] in ROLE_TECHNICAL_TOPICS
        assert len(ROLE_TECHNICAL_TOPICS[profile["role"]]) >= 3
        assert len(profile["skills"]) >= 3


def test_role_names_cover_classic_specialisms():
    names = role_names()
    for expected in ("Software Engineer", "Frontend Developer", "Data Scientist / ML Engineer",
                     "DevOps Engineer", "Mobile Developer", "QA / Test Automation Engineer"):
        assert expected in names


def test_offline_technical_questions_are_role_specific():
    """Each supported role's curated interview questions must actually surface in
    offline Technical questions (count >= pool size returns the whole mixed pool deterministically)."""
    from modules.question_generator import _RECENT, _offline_generate

    for profile in ROLE_PROFILES:
        _RECENT.clear()
        questions = _offline_generate(profile["role"], [], "Medium", "Technical", 25)
        assert questions, profile["role"]
        iq = ROLE_INTERVIEW_QUESTIONS.get(profile["role"], [])
        text = " ".join(q["question"] for q in questions).lower()
        # At least one curated interview question must appear
        assert any(q.lower() in text for q in iq), \
            f"no curated interview question for {profile['role']}"


def test_roles_produce_distinct_question_sets():
    """Two different roles must not get identical Technical question sets."""
    from modules.question_generator import _RECENT, _offline_generate

    _RECENT.clear()
    q1 = {q["question"] for q in _offline_generate("Data Engineer", [], "Medium", "Technical", 25)}
    _RECENT.clear()
    q2 = {q["question"] for q in _offline_generate("UX/UI Designer", [], "Medium", "Technical", 25)}
    assert q1 != q2


def test_unknown_role_still_generates_questions(client):
    from modules.question_generator import _RECENT, _offline_generate

    _RECENT.clear()
    questions = _offline_generate("Principal Chaos Engineer", ["sre"], "Hard", "Technical", 1)
    assert len(questions) == 1
    assert questions[0]["question"]
