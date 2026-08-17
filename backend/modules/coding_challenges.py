"""
Coding Challenges Module
--------------------------
A bank of interview coding questions (Easy / Medium / Hard) with a
sandboxed-ish runner that executes candidate solutions in Python,
JavaScript, Java or C++ against hidden test cases.

Each run happens in a subprocess with a hard timeout, isolated from the
Flask process. Runtimes must be installed on the host:

    Python      — bundled (python)
    JavaScript  — requires Node.js (`node`)
    Java        — requires a JDK (`javac`, `java`)
    C++         — requires a C++17 compiler (`g++`)

If the required runtime/compiler is missing, a friendly error is returned.

NOTE: For a production system, run submissions in a properly isolated
container/sandbox (gVisor, firecracker, Judge0). The subprocess + timeout
approach here is fine for a personal/demo project but should not be exposed
to untrusted public traffic as-is.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Language metadata
# ---------------------------------------------------------------------------

LANGUAGES = {
    "python": {"name": "Python", "ext": "py"},
    "javascript": {"name": "JavaScript", "ext": "js"},
    "java": {"name": "Java", "ext": "java"},
    "cpp": {"name": "C++", "ext": "cpp"},
}

# ---------------------------------------------------------------------------
# Challenge bank
#   `signature` uses portable type tags:
#     int, long, double, string, boolean, int[], long[], double[],
#     string[], boolean[]
# ---------------------------------------------------------------------------

CHALLENGES = [
    # ------------------------------ EASY ------------------------------
    {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "prompt": (
            "Write a function `solve(nums, target)` that returns the indices of the "
            "two numbers in `nums` that add up to `target`. Assume exactly one solution exists."
        ),
        "signature": {"params": [["nums", "int[]"], ["target", "int"]], "returns": "int[]"},
        "test_cases": [
            {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"args": [[3, 2, 4], 6], "expected": [1, 2]},
            {"args": [[3, 3], 6], "expected": [0, 1]},
        ],
    },
    {
        "id": "reverse-string",
        "title": "Reverse a String",
        "difficulty": "Easy",
        "prompt": "Write a function `solve(s)` that returns the string `s` reversed.",
        "signature": {"params": [["s", "string"]], "returns": "string"},
        "test_cases": [
            {"args": ["hello"], "expected": "olleh"},
            {"args": [""], "expected": ""},
            {"args": ["a"], "expected": "a"},
        ],
    },
    {
        "id": "fizzbuzz",
        "title": "FizzBuzz",
        "difficulty": "Easy",
        "prompt": (
            "Write a function `solve(n)` that returns a list of strings from 1 to n where "
            "multiples of 3 are 'Fizz', multiples of 5 are 'Buzz', multiples of both are "
            "'FizzBuzz', otherwise the number as a string."
        ),
        "signature": {"params": [["n", "int"]], "returns": "string[]"},
        "test_cases": [
            {"args": [5], "expected": ["1", "2", "Fizz", "4", "Buzz"]},
            {"args": [15], "expected": ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8",
                                          "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]},
        ],
    },
    {
        "id": "max-element",
        "title": "Maximum Element",
        "difficulty": "Easy",
        "prompt": "Write a function `solve(nums)` that returns the largest value in the array `nums`.",
        "signature": {"params": [["nums", "int[]"]], "returns": "int"},
        "test_cases": [
            {"args": [[3, 7, 2, 9, 5]], "expected": 9},
            {"args": [[-3, -7, -2]], "expected": -2},
            {"args": [[42]], "expected": 42},
        ],
    },
    {
        "id": "count-vowels",
        "title": "Count Vowels",
        "difficulty": "Easy",
        "prompt": "Write a function `solve(s)` that returns the number of vowels (a, e, i, o, u) in `s`.",
        "signature": {"params": [["s", "string"]], "returns": "int"},
        "test_cases": [
            {"args": ["hello world"], "expected": 3},
            {"args": ["aeiou"], "expected": 5},
            {"args": ["xyz"], "expected": 0},
        ],
    },
    {
        "id": "is-palindrome",
        "title": "Palindrome Check",
        "difficulty": "Easy",
        "prompt": "Write a function `solve(s)` that returns True if `s` reads the same forwards and backwards.",
        "signature": {"params": [["s", "string"]], "returns": "boolean"},
        "test_cases": [
            {"args": ["racecar"], "expected": True},
            {"args": ["hello"], "expected": False},
            {"args": [""], "expected": True},
        ],
    },

    # ------------------------------ MEDIUM ------------------------------
    {
        "id": "valid-palindrome",
        "title": "Valid Palindrome",
        "difficulty": "Medium",
        "prompt": (
            "Write a function `solve(s)` that returns True if `s` is a palindrome, ignoring "
            "case and non-alphanumeric characters."
        ),
        "signature": {"params": [["s", "string"]], "returns": "boolean"},
        "test_cases": [
            {"args": ["A man, a plan, a canal: Panama"], "expected": True},
            {"args": ["race a car"], "expected": False},
            {"args": [" "], "expected": True},
        ],
    },
    {
        "id": "binary-search",
        "title": "Binary Search",
        "difficulty": "Medium",
        "prompt": (
            "Write a function `solve(nums, target)` that performs binary search on a sorted "
            "array `nums` and returns the index of `target`, or -1 if not found."
        ),
        "signature": {"params": [["nums", "int[]"], ["target", "int"]], "returns": "int"},
        "test_cases": [
            {"args": [[-1, 0, 3, 5, 9, 12], 9], "expected": 4},
            {"args": [[-1, 0, 3, 5, 9, 12], 2], "expected": -1},
            {"args": [[5], 5], "expected": 0},
        ],
    },
    {
        "id": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "Medium",
        "prompt": (
            "Write a function `solve(s)` that returns True if the brackets in `s` are "
            "correctly closed and nested. Valid pairs: () [] {}."
        ),
        "signature": {"params": [["s", "string"]], "returns": "boolean"},
        "test_cases": [
            {"args": ["()[]{}"], "expected": True},
            {"args": ["(]"], "expected": False},
            {"args": ["([)]"], "expected": False},
            {"args": [""], "expected": True},
        ],
    },
    {
        "id": "is-anagram",
        "title": "Valid Anagram",
        "difficulty": "Medium",
        "prompt": (
            "Write a function `solve(a, b)` that returns True if `b` is an anagram of `a` "
            "(same letters, any order)."
        ),
        "signature": {"params": [["a", "string"], ["b", "string"]], "returns": "boolean"},
        "test_cases": [
            {"args": ["anagram", "nagaram"], "expected": True},
            {"args": ["rat", "car"], "expected": False},
            {"args": ["", ""], "expected": True},
        ],
    },
    {
        "id": "first-non-repeating",
        "title": "First Non-Repeating Character",
        "difficulty": "Medium",
        "prompt": (
            "Write a function `solve(s)` that returns the index of the first character that "
            "does not repeat, or -1 if every character repeats."
        ),
        "signature": {"params": [["s", "string"]], "returns": "int"},
        "test_cases": [
            {"args": ["leetcode"], "expected": 0},
            {"args": ["loveleetcode"], "expected": 2},
            {"args": ["aabb"], "expected": -1},
        ],
    },

    # ------------------------------ HARD ------------------------------
    {
        "id": "longest-substring",
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "Hard",
        "prompt": (
            "Write a function `solve(s)` that returns the length of the longest substring "
            "without repeating characters."
        ),
        "signature": {"params": [["s", "string"]], "returns": "int"},
        "test_cases": [
            {"args": ["abcabcbb"], "expected": 3},
            {"args": ["bbbbb"], "expected": 1},
            {"args": ["pwwkew"], "expected": 3},
            {"args": [""], "expected": 0},
        ],
    },
    {
        "id": "max-water",
        "title": "Container With Most Water",
        "difficulty": "Hard",
        "prompt": (
            "Write a function `solve(height)` where `height[i]` is a bar's height. Return the "
            "maximum area of water a pair of bars can hold (two-pointer)."
        ),
        "signature": {"params": [["height", "int[]"]], "returns": "int"},
        "test_cases": [
            {"args": [[1, 8, 6, 2, 5, 4, 8, 3, 7]], "expected": 49},
            {"args": [[1, 1]], "expected": 1},
            {"args": [[4, 3, 2, 1, 4]], "expected": 16},
        ],
    },
    {
        "id": "subarray-sum",
        "title": "Subarray Sum Equals K",
        "difficulty": "Hard",
        "prompt": (
            "Write a function `solve(nums, k)` that returns the number of contiguous subarrays "
            "whose elements sum to exactly `k`."
        ),
        "signature": {"params": [["nums", "int[]"], ["k", "int"]], "returns": "int"},
        "test_cases": [
            {"args": [[1, 1, 1], 2], "expected": 2},
            {"args": [[1, 2, 3], 3], "expected": 2},
            {"args": [[1], 0], "expected": 0},
        ],
    },
]

# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

_ARRAY_TYPES = {"int[]", "long[]", "double[]", "string[]", "boolean[]"}


def _elem_type(ttype):
    return ttype[:-2] if ttype.endswith("[]") else ttype


def _default_value(ttype):
    if ttype in ("int", "long", "double"):
        return "0"
    if ttype == "boolean":
        return "false"
    if ttype == "string":
        return '""'
    return "{}"  # arrays (C++/Java defaults differ — see starters)


# ---------------------------------------------------------------------------
# Language-specific signature / starter / literal rendering
# ---------------------------------------------------------------------------

_JAVA_TYPES = {
    "int": "int", "long": "long", "double": "double", "string": "String",
    "boolean": "boolean",
    "int[]": "int[]", "long[]": "long[]", "double[]": "double[]",
    "string[]": "String[]", "boolean[]": "boolean[]",
}

_CPP_TYPES = {
    "int": "int", "long": "long long", "double": "double", "string": "std::string",
    "boolean": "bool",
    "int[]": "std::vector<int>", "long[]": "std::vector<long long>",
    "double[]": "std::vector<double>", "string[]": "std::vector<std::string>",
    "boolean[]": "std::vector<bool>",
}

_PY_TYPES = {
    "int": "int", "long": "int", "double": "float", "string": "str",
    "boolean": "bool", "int[]": "list", "long[]": "list", "double[]": "list",
    "string[]": "list", "boolean[]": "list",
}


def _java_literal(value, ttype):
    if ttype == "string":
        return '"' + _escape_quotes(value) + '"'
    if ttype in ("int", "long", "double", "boolean"):
        return str(value).lower() if isinstance(value, bool) else str(value)
    if ttype.endswith("[]"):
        inner = _elem_type(ttype)
        return "new {}[]{{{}}}".format(
            _JAVA_TYPES[inner], ", ".join(_java_literal(v, inner) for v in value)
        )
    raise ValueError(f"unsupported java type {ttype}")


def _cpp_literal(value, ttype):
    if ttype == "string":
        return '"' + _escape_quotes(value) + '"'
    if ttype in ("int", "long", "double", "boolean"):
        return str(value).lower() if isinstance(value, bool) else str(value)
    if ttype.endswith("[]"):
        inner = _elem_type(ttype)
        return "{{{}}}".format(", ".join(_cpp_literal(v, inner) for v in value))
    raise ValueError(f"unsupported cpp type {ttype}")


def _escape_quotes(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Starter code
# ---------------------------------------------------------------------------

def _py_params(signature):
    return ", ".join(name for name, _ in signature["params"])


def _java_params(signature):
    return ", ".join(f"{_JAVA_TYPES[t]} {n}" for n, t in signature["params"])


def _cpp_params(signature):
    parts = []
    for name, ttype in signature["params"]:
        if ttype.endswith("[]"):
            parts.append(f"{_CPP_TYPES[ttype]}& {name}")
        else:
            parts.append(f"{_CPP_TYPES[ttype]} {name}")
    return ", ".join(parts)


def _java_default(ttype):
    if ttype.endswith("[]") or ttype == "string":
        return "null"
    return "0" if ttype in ("int", "long", "double") else "false"


def _cpp_default(ttype):
    if ttype.endswith("[]"):
        return "{}"
    if ttype == "string":
        return '""'
    return "0" if ttype in ("int", "long", "double") else "false"


def _starter_code(challenge, language):
    sig = challenge["signature"]
    returns = _JAVA_TYPES[sig["returns"]] if language == "java" else _CPP_TYPES[sig["returns"]]
    if language == "python":
        return f"def solve({_py_params(sig)}):\n    # your code here\n    pass\n"
    if language == "javascript":
        return f"function solve({_py_params(sig)}) {{\n  // your code here\n}}\n"
    if language == "java":
        return (
            f"static {returns} solve({_java_params(sig)}) {{\n"
            f"    // your code here\n    return {_java_default(sig['returns'])};\n}}\n"
        )
    if language == "cpp":
        return (
            f"{returns} solve({_cpp_params(sig)}) {{\n"
            f"    // your code here\n    return {_cpp_default(sig['returns'])};\n}}\n"
        )
    raise ValueError(f"unsupported language {language}")


# ---------------------------------------------------------------------------
# Runner templates
# ---------------------------------------------------------------------------

PYTHON_TEMPLATE = """
import json, sys

{user_code}

test_cases = {test_cases}
results = []
for tc in test_cases:
    try:
        args = tc["args"]
        expected = tc["expected"]
        actual = {invoke}(*args)
        results.append({{"passed": actual == expected, "actual": actual, "expected": expected}})
    except Exception as e:
        results.append({{"passed": False, "error": str(e), "expected": tc["expected"]}})

print(json.dumps(results, default=str))
"""

JS_TEMPLATE = """
const testCases = {test_cases};

{user_code}

function eq(a, b) {{
  return JSON.stringify(a) === JSON.stringify(b);
}}
const results = testCases.map(tc => {{
  try {{
    const actual = solve(...tc.args);
    return {{ passed: eq(actual, tc.expected), actual, expected: tc.expected }};
  }} catch (e) {{
    return {{ passed: false, error: String(e), expected: tc.expected }};
  }}
}});
process.stdout.write(JSON.stringify(results));
"""

_JAVA_COMPARATOR = {
    "int": "actual == expected",
    "long": "actual == expected",
    "double": "actual == expected",
    "boolean": "actual == expected",
    "string": "actual.equals(expected)",
    "int[]": "java.util.Arrays.equals(actual, expected)",
    "long[]": "java.util.Arrays.equals(actual, expected)",
    "double[]": "java.util.Arrays.equals(actual, expected)",
    "string[]": "java.util.Arrays.equals(actual, expected)",
    "boolean[]": "java.util.Arrays.equals(actual, expected)",
}

_JAVA_TOJSON = {
    "int": "String.valueOf(actual)",
    "long": "String.valueOf(actual)",
    "double": "String.valueOf(actual)",
    "boolean": "String.valueOf(actual)",
    "string": "escape(actual)",
    "int[]": "java.util.Arrays.toString(actual)",
    "long[]": "java.util.Arrays.toString(actual)",
    "double[]": "java.util.Arrays.toString(actual)",
    "boolean[]": "java.util.Arrays.toString(actual)",
    "string[]": "stringArray(actual)",
}


def _java_string_array_to_json():
    return (
        "static String stringArray(String[] a) {\n"
        "    StringBuilder sb = new StringBuilder(\"[\");\n"
        "    for (int i = 0; i < a.length; i++) {\n"
        "        if (i > 0) sb.append(',');\n"
        "        sb.append(escape(a[i]));\n"
        "    }\n"
        "    return sb.append(']').toString();\n"
        "}\n"
    )


def _java_case(challenge, index, invoke="new Solution().solve"):
    sig = challenge["signature"]
    tc = challenge["test_cases"][index]
    returns = sig["returns"]
    params = sig["params"]
    lines = ["        {"]
    for i, (name, ttype) in enumerate(params):
        lines.append(f"            {_JAVA_TYPES[ttype]} {name} = {_java_literal(tc['args'][i], ttype)};")
    lines.append(f"            {_JAVA_TYPES[returns]} actual = {invoke}({', '.join(n for n, _ in params)});")
    lines.append(f"            {_JAVA_TYPES[returns]} expected = {_java_literal(tc['expected'], returns)};")
    lines.append(f"            boolean passed = {_JAVA_COMPARATOR[returns]};")
    lines.append(
        '            out.append("{\\"passed\\":").append(passed)'
        f'.append(",\\"actual\\":").append({_JAVA_TOJSON[returns]})'
        f'.append(",\\"expected\\":").append({_JAVA_TOJSON[returns].replace("actual", "expected")})'
        '.append("}");'
    )
    lines.append("        }")
    return "\n".join(lines)


def _split_java_imports(user_code):
    """Hoist top-level import statements out of the code body (Java forbids them
    inside a class). Returns (import_block, remaining_code)."""
    imports = re.findall(r"^\s*import\s+[\w.*]+\s*;", user_code, flags=re.MULTILINE)
    rest = re.sub(r"^\s*import\s+[\w.*]+\s*;", "", user_code, flags=re.MULTILINE)
    return "\n".join(imports), rest.strip()


def _wrap_user_solution(user_code):
    """Return (body, invoke_expr) where `body` is Java code that defines a
    static class Solution, supporting both bare-method starter style and
    LeetCode-style `class Solution { ... }` submissions."""
    imports, rest = _split_java_imports(user_code)
    if re.search(r"\bclass\s+Solution\b", rest):
        body = re.sub(r"\b(?:public\s+)?class\s+(Solution)\b", r"static class \1", rest, count=1)
    else:
        body = f"static class Solution {{\n{rest}\n}}"
    return imports, body


def _java_source(challenge, user_code):
    sig = challenge["signature"]
    needs_string_array = sig["returns"] == "string[]"
    helper = _java_string_array_to_json() if needs_string_array else ""
    cases = "\n".join(_java_case(challenge, i) for i in range(len(challenge["test_cases"])))
    escape_fn = (
        "    static String escape(String s) {\n"
        "        return s == null ? \"null\" : \"\\\"\" + s.replace(\"\\\\\", \"\\\\\\\\\")\n"
        "            .replace(\"\\\"\", \"\\\\\\\"\").replace(\"\\n\", \"\\\\n\") + \"\\\"\";\n"
        "    }\n"
    )
    imports, user_class = _wrap_user_solution(user_code)
    return f"""{imports}
import java.util.*;

public class Main {{
    {user_class}

    {escape_fn}
    {helper}
    public static void main(String[] args) {{
        StringBuilder out = new StringBuilder();
        try {{
{cases}
        }} catch (Throwable e) {{
            out.append("{{\\"passed\\":false,\\"error\\":\\"exception\\"}}");
        }}
        System.out.println("[" + out + "]");
    }}
}}
"""


def _cpp_case(challenge, index):
    sig = challenge["signature"]
    tc = challenge["test_cases"][index]
    returns = sig["returns"]
    params = sig["params"]
    lines = ["    {"]
    for i, (name, ttype) in enumerate(params):
        lit = _cpp_literal(tc["args"][i], ttype)
        lines.append(f"        {_CPP_TYPES[ttype]} {name} = {lit};")
    args = ", ".join(n for n, _ in params)
    lines.append(f"        auto actual = solve({args});")
    if returns.endswith("[]"):
        lines.append(f"        {_CPP_TYPES[returns]} expected = {_cpp_literal(tc['expected'], returns)};")
        lines.append("        bool passed = vecEq(actual, expected);")
        out = '        out += "{\\"passed\\":" + string(passed ? "true" : "false")'
        out += ' + ",\\"actual\\":" + toJson(actual) + ",\\"expected\\":" + toJson(expected) + "}";'
        lines.append(out)
    elif returns == "string":
        lines.append('        auto expected = std::string{""} + ' + _cpp_literal(tc['expected'], returns) + ";")
        lines.append("        bool passed = actual == expected;")
        out = '        out += "{\\"passed\\":" + string(passed ? "true" : "false")'
        out += ' + ",\\"actual\\":" + js(actual) + ",\\"expected\\":" + js(expected) + "}";'
        lines.append(out)
    else:
        lines.append(f"        auto expected = {_cpp_literal(tc['expected'], returns)};")
        lines.append("        bool passed = actual == expected;")
        if returns == "boolean":
            out = '        out += "{\\"passed\\":" + string(passed ? "true" : "false")'
            out += ' + ",\\"actual\\":" + string(actual ? "true" : "false")'
            out += ' + ",\\"expected\\":" + string(expected ? "true" : "false") + "}";'
        else:
            out = '        out += "{\\"passed\\":" + string(passed ? "true" : "false")'
            out += ' + ",\\"actual\\":" + std::to_string(actual)'
            out += ' + ",\\"expected\\":" + std::to_string(expected) + "}";'
        lines.append(out)
    lines.append('        out += ",";')
    lines.append("    }")
    return "\n".join(lines)


def _cpp_source(challenge, user_code):
    cases = "\n".join(_cpp_case(challenge, i) for i in range(len(challenge["test_cases"])))
    return f"""#include <bits/stdc++.h>
using namespace std;

{user_code}

template <typename T>
bool vecEq(const vector<T>& a, const vector<T>& b) {{
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); i++) if (!(a[i] == b[i])) return false;
    return true;
}}

string js(const string& s) {{
    string r = "\\"";
    for (char c : s) {{
        if (c == '"') r += "\\\\\\"";
        else if (c == '\\\\') r += "\\\\\\\\";
        else r += c;
    }}
    r += "\\"";
    return r;
}}

template <typename T>
string toJson(const vector<T>& v) {{
    string r = "[";
    for (size_t i = 0; i < v.size(); i++) {{
        if (i) r += ",";
        r += to_string(v[i]);
    }}
    return r + "]";
}}

string toJson(const vector<string>& v) {{
    string r = "[";
    for (size_t i = 0; i < v.size(); i++) {{
        if (i) r += ",";
        r += js(v[i]);
    }}
    return r + "]";
}}

string toJson(const vector<bool>& v) {{
    string r = "[";
    for (size_t i = 0; i < v.size(); i++) {{
        if (i) r += ",";
        r += v[i] ? "true" : "false";
    }}
    return r + "]";
}}

int main() {{
    string out;
    {cases}
    if (!out.empty()) out.pop_back();
    cout << "[" << out << "]" << endl;
    return 0;
}}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_challenge(challenge_id):
    return next((c for c in CHALLENGES if c["id"] == challenge_id), None)


def get_languages():
    return [{"id": lid, "name": meta["name"]} for lid, meta in LANGUAGES.items()]


def _sample_value(value):
    """Render a value as a human-readable Python-style literal for sample I/O."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(_sample_value(v) for v in value) + "]"
    return str(value)


def _samples(challenge, limit=2):
    """Sample input/output pairs (calls into `solve`) taken from the test cases."""
    samples = []
    for tc in challenge["test_cases"][:limit]:
        args = ", ".join(_sample_value(v) for v in tc["args"])
        samples.append({"input": f"solve({args})", "output": _sample_value(tc["expected"])})
    return samples


def list_challenges(language="python"):
    """Public challenge list with starter code generated for the given language."""
    language = _normalize_language(language)
    return [
        {
            "id": c["id"],
            "title": c["title"],
            "difficulty": c["difficulty"],
            "prompt": c["prompt"],
            "starter_code": _starter_code(c, language),
            "signature": c["signature"],
            "samples": _samples(c),
        }
        for c in CHALLENGES
    ]


def _normalize_language(language):
    lang = (language or "python").strip().lower()
    aliases = {"py": "python", "js": "javascript", "node": "javascript", "c++": "cpp", "c": "cpp"}
    return aliases.get(lang, lang)


def _python_invoke(user_code):
    """LeetCode-style submissions wrap the solution in `class Solution`."""
    if re.search(r"\bclass\s+Solution\b", user_code):
        return "Solution().solve"
    return "solve"


def _build_source(language, challenge, user_code):
    test_cases = json.dumps(challenge["test_cases"])
    if language == "python":
        return PYTHON_TEMPLATE.format(
            user_code=user_code,
            test_cases=test_cases,
            invoke=_python_invoke(user_code),
        )
    if language == "javascript":
        return JS_TEMPLATE.format(user_code=user_code, test_cases=test_cases)
    if language == "java":
        return _java_source(challenge, user_code)
    if language == "cpp":
        return _cpp_source(challenge, user_code)
    raise ValueError(f"unsupported language {language}")


def _parse_result(output):
    output = output.strip()
    lines = [ln for ln in output.splitlines() if ln.strip()]
    if not lines:
        return {"error": "No output produced by the runner"}
    try:
        return json.loads(lines[-1])
    except (json.JSONDecodeError, IndexError):
        return {"error": f"Could not parse runner output: {output[-300:]}"}


def run_submission(challenge_id, user_code, language="python", timeout=5):
    language = _normalize_language(language)
    if language not in LANGUAGES:
        return {"error": f"Unsupported language '{language}'. Supported: {', '.join(LANGUAGES)}"}, 400

    challenge = get_challenge(challenge_id)
    if not challenge:
        return {"error": "Challenge not found"}, 404

    if not (user_code or "").strip():
        return {"error": "code is required"}, 400

    source = _build_source(language, challenge, user_code)
    workdir = tempfile.mkdtemp(prefix="sip_code_")
    cleanup = None
    try:
        prepared = _prepare_program(language, source, workdir)
        if isinstance(prepared[0], dict):  # (error_dict, status_code) tuple
            return prepared
        program, cleanup = prepared
        proc = subprocess.run(  # noqa: S603 — untrusted code runs in a subprocess sandbox (see module docstring)
            program,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
        if proc.returncode != 0:
            details = proc.stderr[-1500:] if proc.stderr else "unknown error"
            return {"error": "Runtime error", "details": details}, 400

        results = _parse_result(proc.stdout)
        if isinstance(results, dict) and results.get("error"):
            return results, 400

        passed = sum(1 for r in results if r.get("passed"))
        total = len(results)
        return {
            "challenge_id": challenge_id,
            "language": language,
            "passed": passed,
            "total": total,
            "score_percent": round(passed / total * 100, 1) if total else 0,
            "results": results,
        }, 200
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out"}, 400
    except FileNotFoundError:
        return {"error": f"Runtime for '{language}' is not installed on this server."}, 400
    except Exception as e:
        return {"error": str(e)}, 400
    finally:
        if cleanup is not None:
            cleanup()


def _prepare_program(language, source, workdir):
    """Write source to disk and return (command_list, cleanup_fn)."""
    ext = LANGUAGES[language]["ext"]
    script_path = os.path.join(workdir, f"Main.{ext}")

    def cleanup():
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except OSError:
            pass

    if language in ("python", "javascript"):
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(source)
        if language == "python":
            return [sys.executable, script_path], cleanup
        return ["node", script_path], cleanup

    if language == "java":
        with open(os.path.join(workdir, "Main.java"), "w", encoding="utf-8") as f:
            f.write(source)
        try:
            subprocess.run(  # noqa: S603, S607 — compile step inside the sandbox workdir
                ["javac", "Main.java"], cwd=workdir, capture_output=True, text=True, timeout=15
            )
        except FileNotFoundError:
            return {"error": "Runtime for 'java' is not installed on this server."}, 400
        if not os.path.exists(os.path.join(workdir, "Main.class")):
            return {"error": "Compilation failed", "details": "Check your code for syntax errors."}, 400
        return ["java", "-cp", workdir, "Main"], cleanup

    # C++
    src = os.path.join(workdir, "main.cpp")
    exe = os.path.join(workdir, "main.exe" if os.name == "nt" else "main")
    with open(src, "w", encoding="utf-8") as f:
        f.write(source)
    try:
        subprocess.run(  # noqa: S603, S607 — compile step inside the sandbox workdir
            ["g++", "-std=c++17", src, "-o", exe], cwd=workdir, capture_output=True, text=True, timeout=20
        )
    except FileNotFoundError:
        return {"error": "Runtime for 'cpp' is not installed on this server."}, 400
    if not os.path.exists(exe):
        return {"error": "Compilation failed", "details": "Check your code for syntax errors."}, 400
    return [exe], cleanup
