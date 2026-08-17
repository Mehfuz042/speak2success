"""Coding-challenge runner error handling and harness generation."""
import os
import subprocess
import tempfile

import pytest
from conftest import _create_session

from modules import coding_challenges


def _answer_payload(question, category="Technical", round_id="technical"):
    return {
        "round_id": round_id,
        "question": question,
        "category": category,
        "answer": "I shipped the feature on time and cut rollout time by 40 percent.",
        "duration_seconds": 15,
    }


def test_runner_returns_clean_error_when_runtime_missing(monkeypatch):
    """A missing runtime (e.g. javac/g++ not installed) must not crash the endpoint."""
    def _missing_runtime(language, source, workdir):
        return {"error": f"Runtime for '{language}' is not installed on this server."}, 400

    monkeypatch.setattr(coding_challenges, "_prepare_program", _missing_runtime)
    res, status = coding_challenges.run_submission("two-sum", "class Solution {}", language="java")
    assert status == 400
    assert "Runtime for 'java'" in res["error"]


def test_coding_submission_with_missing_runtime_returns_400(client, monkeypatch):
    """The full HTTP path must surface the runner error as a clean 400, not a 500."""
    monkeypatch.setattr(
        coding_challenges,
        "_prepare_program",
        lambda language, source, workdir: (
            {"error": "Runtime for 'java' is not installed on this server."},
            400,
        ),
    )
    session = _create_session(client).get_json()["session"]
    coding = next(q for q in session["rounds"][1]["questions"] if q["type"] == "coding")

    res = client.post(
        f"/api/sessions/{session['id']}/coding",
        json={
            "challenge_id": coding["challenge_id"],
            "language": "java",
            "title": coding["title"],
            "difficulty": coding["difficulty"],
            "round_id": "technical",
            "code": "class Solution {}",
        },
    )
    assert res.status_code == 400
    assert "not installed" in res.get_json()["error"]


# ---------------------------------------------------------------------------
# Harness generation (no runtime needed)
# ---------------------------------------------------------------------------

def test_java_source_wraps_leetcode_style_class():
    code = (
        "import java.util.HashMap;\n"
        "class Solution {\n"
        "  public int[] solve(int[] nums, int target) { return nums; }\n"
        "}\n"
    )
    src = coding_challenges._java_source(coding_challenges.get_challenge("two-sum"), code)
    assert "static class Solution {" in src
    assert "new Solution().solve(" in src
    assert "import java.util.HashMap;" in src
    assert "public class Main {" in src


def test_java_source_wraps_bare_method():
    code = "static int[] solve(int[] nums, int target) { return nums; }\n"
    src = coding_challenges._java_source(coding_challenges.get_challenge("two-sum"), code)
    assert "static class Solution {" in src
    assert "static int[] solve(int[] nums, int target)" in src
    assert "new Solution().solve(" in src


def test_python_invoke_detects_class_style():
    assert coding_challenges._python_invoke("class Solution:\n    pass\n") == "Solution().solve"
    assert coding_challenges._python_invoke("def solve(nums):\n    pass\n") == "solve"


def test_python_class_style_solution_runs():
    code = (
        "class Solution:\n"
        "    def solve(self, nums, target):\n"
        "        seen = {}\n"
        "        for i, n in enumerate(nums):\n"
        "            if target - n in seen:\n"
        "                return [seen[target - n], i]\n"
        "            seen[n] = i\n"
        "        return []\n"
    )
    res, status = coding_challenges.run_submission("two-sum", code, language="python")
    assert status == 200
    assert res["passed"] == res["total"]


def test_python_bare_function_runs():
    code = (
        "def solve(nums, target):\n"
        "    for i in range(len(nums)):\n"
        "        for j in range(i + 1, len(nums)):\n"
        "            if nums[i] + nums[j] == target:\n"
        "                return [i, j]\n"
    )
    res, status = coding_challenges.run_submission("two-sum", code, language="python")
    assert status == 200
    assert res["passed"] == res["total"]


# ---------------------------------------------------------------------------
# Java end-to-end (skipped when the local JDK is missing/broken)
# ---------------------------------------------------------------------------

def _java_available():
    if not __import__("shutil").which("javac"):
        return False
    d = tempfile.mkdtemp(prefix="sip_javac_probe_")
    try:
        with open(os.path.join(d, "Probe.java"), "w", encoding="utf-8") as f:
            f.write("public class Probe {}\n")
        javac = os.environ.get("JAVAC", "javac")
        p = subprocess.run(  # noqa: S603, S607
            [javac, "Probe.java"], cwd=d, capture_output=True, text=True, timeout=15  # noqa: S603, S607
        )
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        import shutil

        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.skipif(not _java_available(), reason="javac is not installed or broken")
def test_java_class_style_solution_runs():
    code = (
        "import java.util.HashMap;\n"
        "import java.util.Map;\n"
        "class Solution {\n"
        "  public int[] solve(int[] nums, int target) {\n"
        "    Map<Integer,Integer> m = new HashMap<>();\n"
        "    for (int i = 0; i < nums.length; i++) {\n"
        "      int c = target - nums[i];\n"
        "      if (m.containsKey(c)) return new int[]{m.get(c), i};\n"
        "      m.put(nums[i], i);\n"
        "    }\n"
        "    return new int[]{};\n"
        "  }\n"
        "}\n"
    )
    res, status = coding_challenges.run_submission("two-sum", code, language="java")
    assert status == 200
    assert res["passed"] == res["total"]
