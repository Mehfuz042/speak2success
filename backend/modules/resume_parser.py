"""
Resume Parser Module
---------------------
Extracts raw text from PDF/TXT resumes and pulls out a rough skill/role
profile using keyword matching. No paid API required.
"""
import re

from PyPDF2 import PdfReader

from .job_roles import ROLE_HINTS

# A reasonably broad skill dictionary. Extend as needed.
SKILL_KEYWORDS = {
    "languages": ["python", "java", "javascript", "typescript", "c++", "c#", "c ",
                  "php", "go", "golang", "ruby", "swift", "kotlin", "sql", "r "],
    "web": ["react", "angular", "vue", "next.js", "node.js", "express", "flask",
            "django", "fastapi", "html", "css", "tailwind", "bootstrap", "redux"],
    "data": ["pandas", "numpy", "matplotlib", "scikit-learn", "sklearn",
             "tensorflow", "pytorch", "keras", "opencv", "nlp", "machine learning",
             "deep learning", "data analysis", "power bi", "tableau"],
    "bigdata": ["spark", "kafka", "airflow", "hadoop", "etl", "snowflake", "dbt",
                "databricks", "data pipelines", "data warehouse"],
    "database": ["mongodb", "mysql", "postgresql", "postgres", "sqlite",
                 "oracle", "redis", "firebase", "dynamodb", "sql server"],
    "cloud_devops": ["aws", "azure", "gcp", "docker", "kubernetes", "jenkins",
                      "ci/cd", "git", "github", "gitlab", "terraform", "ansible", "linux"],
    "infra_reliability": ["prometheus", "grafana", "nginx", "sre", "slo", "incident",
                          "on-call", "chaos engineering", "capacity planning"],
    "testing": ["selenium", "cypress", "playwright", "junit", "pytest", "jest",
                "test automation", "qa", "unit testing"],
    "security": ["penetration testing", "owasp", "vulnerability", "splunk",
                 "cryptography", "zero trust", "secure code review", "threat modeling"],
    "mobile": ["kotlin", "swift", "flutter", "react native", "android", "ios", "dart"],
    "game": ["unity", "unreal", "godot", "opengl", "game", "gameplay", "physics"],
    "design": ["figma", "sketch", "photoshop", "wireframe", "prototype",
               "usability", "design system", "user research"],
    "blockchain": ["solidity", "ethereum", "web3", "smart contract", "defi", "hardhat"],
    "product_agile": ["scrum", "kanban", "agile", "jira", "sprint", "product management",
                      "roadmap", "user research", "a/b testing", "stakeholder"],
    "soft": ["leadership", "communication", "teamwork", "problem solving",
             "agile", "scrum", "project management"],
}


def extract_text(file_stream, filename: str) -> str:
    """Extract raw text from an uploaded PDF or plain-text file stream."""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        return text
    # fallback: treat as plain text
    raw = file_stream.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    return raw


def _compile_patterns(keywords):
    """Compile word-boundary regexes so short keywords (go, r, c) don't match inside other words."""
    patterns = []
    for kw in keywords:
        patterns.append(re.compile(rf"(?<!\w){re.escape(kw.strip())}(?!\w)", re.IGNORECASE))
    return patterns


def extract_skills(text: str):
    text_lower = text.lower()
    found = {}
    for category, keywords in SKILL_KEYWORDS.items():
        patterns = _compile_patterns(keywords)
        matches = sorted({kw.strip() for kw, pat in zip(keywords, patterns, strict=True) if pat.search(text_lower)})
        if matches:
            found[category] = matches
    return found


def guess_roles(found_skills: dict, top_n: int = 2):
    flat_skills = set()
    for skills in found_skills.values():
        flat_skills.update(skills)

    scores = []
    for role, hints in ROLE_HINTS.items():
        score = sum(1 for h in hints if h in flat_skills)
        if score > 0:
            scores.append((role, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scores[:top_n]] or ["Software Engineer"]


def extract_experience_years(text: str):
    """Very rough heuristic: look for patterns like '2 years', '3+ years'."""
    matches = re.findall(r"(\d+)\+?\s*years?", text.lower())
    years = [int(m) for m in matches if int(m) < 40]
    return max(years) if years else 0


def parse_resume(file_stream, filename: str) -> dict:
    text = extract_text(file_stream, filename)
    skills = extract_skills(text)
    roles = guess_roles(skills)
    experience_years = extract_experience_years(text)
    return {
        "raw_text_preview": text[:2000],
        "skills": skills,
        "suggested_roles": roles,
        "experience_years": experience_years,
        "word_count": len(text.split()),
    }
