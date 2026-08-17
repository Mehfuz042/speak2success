"""
Feedback Engine Module
------------------------
Scores a candidate's answer to an interview question and produces personalized
improvement suggestions. Uses Gemini when configured, otherwise a transparent
rule-based heuristic scorer that checks structure (incl. the STAR method),
filler words, confidence, question-type relevance, and **mindset analysis**.
"""
import json

from .ai_config import get_client, is_configured, model_name

FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "actually",
                "sort of", "kind of", "i mean", "so yeah"]

WEAK_OPENERS = ["i don't know", "i'm not sure", "maybe", "i guess", "not sure"]

STAR_MARKERS = {
    "situation": ["situation", "context", "when i", "at my previous", "in my last",
                  "back when", "during my time", "at my current"],
    "task": ["task", "responsibility", "goal", "objective", "i had to", "i was asked",
             "my role was", "i was responsible"],
    "action": ["i did", "i built", "i created", "i implemented", "i led", "i improved",
               "i designed", "i developed", "i took", "i reduced", "i increased", "i fixed",
               "i proposed", "i organized", "i managed", "i coordinated", "i launched"],
    "result": ["as a result", "result", "outcome", "impact", "in the end", "afterwards",
               "this led", "resulted in", "improved", "increased", "decreased", "reduced",
               "saved", "generated", "delivered", "achieved", "reached"],
}

# Question-type detection patterns
QUESTION_TYPES = {
    "behavioral": ["tell me about a time", "describe a situation", "give an example",
                   "how did you handle", "what happened when", "recall a time"],
    "technical": ["explain", "what is", "how does", "describe the", "difference between",
                  "how would you design", "what are the", "compare"],
    "situational": ["what would you do", "how would you handle", "if you were",
                    "suppose you", "imagine a scenario", "how would you approach"],
    "self_reflection": ["what are your strengths", "what are your weaknesses",
                        "why do you want", "where do you see yourself", "what motivates",
                        "what drives you", "tell me about yourself"],
}

# Role-specific keywords for content relevance
ROLE_KEYWORDS = {
    "Software Engineer": ["code", "algorithm", "system", "design", "test", "debug", "deploy"],
    "Frontend Developer": ["ui", "component", "render", "css", "responsive", "browser", "dom"],
    "Backend Developer": ["api", "database", "server", "endpoint", "authentication", "cache"],
    "Data Scientist / ML Engineer": ["model", "data", "training", "accuracy", "feature", "metric"],
    "Data Analyst": ["analysis", "sql", "dashboard", "metric", "insight", "visualization"],
    "DevOps Engineer": ["pipeline", "deploy", "infrastructure", "monitoring", "container", "cloud"],
    "Product Manager": ["user", "feature", "priority", "metric", "roadmap", "stakeholder"],
}


def _detect_question_type(question_lower):
    """Detect the type of interview question based on phrasing."""
    for qtype, patterns in QUESTION_TYPES.items():
        if any(p in question_lower for p in patterns):
            return qtype
    return "general"


def _star_analysis(answer_lower):
    """Return which STAR pillars the answer touches, based on keyword markers."""
    found = {}
    for pillar, markers in STAR_MARKERS.items():
        if any(marker in answer_lower for marker in markers):
            found[pillar] = True
    return found


def _detect_metrics(answer_lower):
    """Check if the answer includes quantifiable results."""
    import re
    metrics_patterns = [
        r'\d+%', r'\$\d+', r'\d+x', r'\d+ percent',
        r'reduced .+ by \d+', r'increased .+ by \d+',
        r'saved .+ \d+', r'improved .+ by \d+',
        r'\d+ (?:users|customers|clients|hours|days|weeks|months)',
        r'\d+ (?:requests|errors|bugs|incidents)',
    ]
    return any(re.search(p, answer_lower) for p in metrics_patterns)


# ---------------------------------------------------------------------------
# Mindset Analysis
# ---------------------------------------------------------------------------

MINDSET_TRAITS = {
    "growth_mindset": {
        "label": "Growth Mindset",
        "positive": [
            "i learned", "i grew", "i improved", "i developed", "i evolved",
            "i studied", "i practiced", "i adapted", "i picked up", "i taught myself",
            "i became better", "i refined", "i honed", "i mastered", "i upskilled",
            "i embraced", "i challenged myself", "i stepped outside",
        ],
        "negative": [
            "i already knew", "i was born with", "it came naturally",
            "i've always been", "i'm just naturally", "i don't need to",
            "that's just how i am", "i can't change",
        ],
    },
    "ownership": {
        "label": "Ownership & Accountability",
        "positive": [
            "i led", "i owned", "i was responsible", "i drove", "i initiated",
            "i decided", "i took charge", "i made sure", "i ensured", "i committed",
            "i delivered", "i executed", "i managed", "i built", "i created",
        ],
        "negative": [
            "they told me to", "i was told", "someone else", "not my job",
            "i just followed", "i had no choice", "they made me",
            "it wasn't my decision", "i was assigned",
        ],
    },
    "problem_solving": {
        "label": "Problem-Solving Approach",
        "positive": [
            "first i analyzed", "i broke down", "i identified the root cause",
            "i explored options", "i evaluated", "i tested", "i iterated",
            "i prototyped", "i researched", "i investigated", "i benchmarked",
            "i considered", "i weighed", "i hypothesized", "i validated",
        ],
        "negative": [
            "i just guessed", "i hoped for the best", "i tried randomly",
            "i didn't know where to start", "i panicked", "i gave up",
            "i avoided", "i ignored it", "i hoped it would fix itself",
        ],
    },
    "adaptability": {
        "label": "Adaptability & Resilience",
        "positive": [
            "i adapted", "i pivoted", "i adjusted", "i pivoted", "i changed",
            "i modified", "i restructured", "i reorganized", "i recovered",
            "i bounced back", "i persisted", "i kept going", "i overcame",
            "i embraced change", "i turned it around", "i found a way",
        ],
        "negative": [
            "i couldn't handle", "i gave up", "i quit", "i surrendered",
            "i stopped trying", "i was overwhelmed", "i froze",
            "i didn't know what to do", "i was stuck",
        ],
    },
    "collaboration": {
        "label": "Collaboration & Teamwork",
        "positive": [
            "we worked together", "we collaborated", "i helped", "i supported",
            "i listened", "i facilitated", "i encouraged", "i mentored",
            "i coached", "i paired", "i synced", "i communicated", "i shared",
            "i gathered input", "i brought the team", "i aligned",
        ],
        "negative": [
            "i did it alone", "i didn't need help", "i worked in isolation",
            "nobody helped", "i didn't trust", "i avoided the team",
            "i went solo", "i didn't consult",
        ],
    },
    "self_awareness": {
        "label": "Self-Awareness",
        "positive": [
            "i realized", "i recognized", "i understood", "i acknowledged",
            "i reflected", "i noticed", "i was wrong", "i made a mistake",
            "i could have done better", "i should have", "i learned that",
            "in hindsight", "looking back", "i underestimated",
        ],
        "negative": [
            "i never make mistakes", "i'm always right", "i know everything",
            "there was nothing wrong", "i don't have weaknesses",
            "i can't think of any", "i'm perfect at",
        ],
    },
    "initiative": {
        "label": "Initiative & Proactivity",
        "positive": [
            "i proposed", "i suggested", "i volunteered", "i took the lead",
            "i proactively", "i went beyond", "i initiated", "i started",
            "i created", "i launched", "i introduced", "i pioneered",
            "i identified an opportunity", "i saw a chance",
        ],
        "negative": [
            "i waited", "i was told to", "i was asked", "i had no choice",
            "i just did what was asked", "i followed orders",
        ],
    },
    "data_driven": {
        "label": "Data-Driven Thinking",
        "positive": [
            "i measured", "i tracked", "i analyzed", "i looked at the data",
            "i checked the metrics", "i benchmarked", "i compared",
            "i used data", "the data showed", "metrics indicated",
            "a/b test", "experiment", "hypothesis", "correlation",
        ],
        "negative": [
            "i just felt", "i assumed", "i guessed", "i went with my gut",
            "i didn't check", "i didn't measure", "no data was available",
        ],
    },
}


def _analyze_mindset(answer_lower):
    """
    Analyze the candidate's mindset from their answer.

    Returns a dict with per-trait scores (0-10), dominant traits,
    growth areas, and an overall mindset profile.
    """
    traits = {}
    for trait_id, trait_def in MINDSET_TRAITS.items():
        pos_count = sum(1 for m in trait_def["positive"] if m in answer_lower)
        neg_count = sum(1 for m in trait_def["negative"] if m in answer_lower)
        # Score: 5 is neutral, positive markers add, negative subtract
        score = max(1.0, min(10.0, 5.0 + pos_count * 1.2 - neg_count * 1.5))
        score = round(score, 1)
        traits[trait_id] = {
            "label": trait_def["label"],
            "score": score,
            "positive_signals": pos_count,
            "negative_signals": neg_count,
        }

    # Sort by score
    sorted_traits = sorted(traits.items(), key=lambda x: x[1]["score"], reverse=True)
    dominant = [t[1]["label"] for t in sorted_traits[:3] if t[1]["score"] >= 7.0]
    growth_areas = [t[1]["label"] for t in sorted_traits[-3:] if t[1]["score"] < 5.0]

    # Overall mindset score (average of all traits)
    scores = [t["score"] for t in traits.values()]
    overall = round(sum(scores) / len(scores), 1) if scores else 5.0

    return {
        "overall_score": overall,
        "traits": traits,
        "dominant_traits": dominant,
        "growth_areas": growth_areas,
    }


def _mindset_feedback(mindset):
    """Generate actionable suggestions based on mindset analysis."""
    suggestions = []
    for trait_id, trait in mindset["traits"].items():
        if trait["score"] < 4.0:
            if trait_id == "growth_mindset":
                suggestions.append("Show more learning language — mention courses, self-study, or skills you developed.")
            elif trait_id == "ownership":
                suggestions.append("Use more ownership language — say 'I led', 'I decided', 'I ensured' instead of passive phrasing.")
            elif trait_id == "problem_solving":
                suggestions.append("Describe your problem-solving process step by step — analysis, options, decision, result.")
            elif trait_id == "adaptability":
                suggestions.append("Highlight how you adapted to change or bounced back from setbacks.")
            elif trait_id == "collaboration":
                suggestions.append("Mention how you worked with others — mentoring, pairing, gathering input.")
            elif trait_id == "self_awareness":
                suggestions.append("Show self-reflection — acknowledge mistakes and what you learned from them.")
            elif trait_id == "initiative":
                suggestions.append("Demonstrate initiative — describe times you went beyond your assigned role.")
            elif trait_id == "data_driven":
                suggestions.append("Reference data, metrics, or experiments that guided your decisions.")
    return suggestions[:4]


def _content_quality(answer_lower, question_type):
    """Assess content quality based on answer depth and relevance."""
    quality = 0.0
    word_count = len(answer_lower.split())

    # Depth indicators
    depth_markers = [
        "for example", "specifically", "in particular", "such as",
        "one time", "another time", "additionally", "moreover",
        "because", "therefore", "consequently", "as a result",
    ]
    depth_score = sum(1 for m in depth_markers if m in answer_lower)
    quality += min(2.0, depth_score * 0.4)

    # Specificity: named tools, frameworks, methodologies
    specificity_markers = [
        "react", "python", "sql", "aws", "docker", "kubernetes",
        "agile", "scrum", "kanban", "ci/cd", "jira", "figma",
        "tensorflow", "pytorch", "spark", "kafka",
    ]
    specificity_score = sum(1 for m in specificity_markers if m in answer_lower)
    quality += min(1.5, specificity_score * 0.5)

    # Question-type specific bonuses
    if question_type == "behavioral":
        if _star_analysis(answer_lower):
            quality += 1.0
        if _detect_metrics(answer_lower):
            quality += 1.0
    elif question_type == "technical":
        technical_depth = ["because", "trade-off", "advantage", "disadvantage",
                          "performance", "scalability", "maintainability"]
        if any(t in answer_lower for t in technical_depth):
            quality += 1.0
    elif question_type == "situational":
        if any(w in answer_lower for w in ["first", "then", "next", "finally", "step"]):
            quality += 1.0

    return round(min(5.0, quality), 1)


def _rule_based_score(question, answer):
    answer_lower = answer.lower().strip()
    word_count = len(answer.split())
    question_lower = question.lower().strip()
    question_type = _detect_question_type(question_lower)

    filler_count = sum(answer_lower.count(f) for f in FILLER_WORDS)
    has_weak_opener = any(answer_lower.startswith(w) for w in WEAK_OPENERS)
    has_structure = any(marker in answer_lower for marker in
                         ["first", "second", "for example", "specifically", "because",
                          "additionally", "moreover", "finally"])
    star = _star_analysis(answer_lower)
    content = _content_quality(answer_lower, question_type)
    has_metrics = _detect_metrics(answer_lower)

    # Base score
    score = 5.0

    # Word count scoring (question-type aware)
    if question_type == "behavioral":
        if word_count < 30:
            score -= 2.0
        elif 60 <= word_count <= 200:
            score += 1.5
        elif word_count > 300:
            score -= 0.5
    elif question_type == "technical":
        if word_count < 20:
            score -= 1.5
        elif 40 <= word_count <= 150:
            score += 1.0
        elif word_count > 250:
            score -= 0.5
    else:
        if word_count < 15:
            score -= 2.0
        elif 30 <= word_count <= 180:
            score += 1.0
        elif word_count > 250:
            score -= 1.0

    # Filler words
    score -= min(filler_count * 0.4, 2.0)

    # Weak opener
    score -= 1.5 if has_weak_opener else 0

    # Structure
    score += 1.0 if has_structure else 0

    # STAR method (weighted by question type)
    if question_type == "behavioral":
        star_weight = 1.5
    else:
        star_weight = 0.5
    if len(star) >= 3:
        score += star_weight
    elif star:
        score += star_weight * 0.3

    # Content quality
    score += content * 0.3

    # Metrics bonus
    if has_metrics:
        score += 0.5

    score = max(1, min(10, round(score, 1)))

    # Generate suggestions
    suggestions = []
    if word_count < 15:
        suggestions.append("Your answer is quite short — add a concrete example or more detail.")
    elif word_count < 30 and question_type == "behavioral":
        suggestions.append("Behavioral answers work best with specific examples — aim for 60-200 words.")

    if filler_count > 2:
        suggestions.append(
            f"Try to reduce filler words (detected ~{filler_count}); "
            "pause instead of saying 'um'/'like'."
        )

    if has_weak_opener:
        suggestions.append("Avoid opening with uncertainty ('I don't know', 'maybe') — lead with confidence.")

    if not has_structure and len(star) < 2:
        suggestions.append("Structure your answer (e.g. Situation → Action → Result, or First/Second/Finally).")

    if star and len(star) < 4:
        missing = [p for p in ("situation", "task", "action", "result") if p not in star]
        suggestions.append(
            f"Your answer touches {', '.join(sorted(star))}. Add the missing "
            f"'{', '.join(missing)}' parts to complete the STAR method."
        )

    if not has_metrics and question_type in ("behavioral", "situational"):
        suggestions.append("Include quantifiable results (e.g., 'reduced load time by 40%', 'increased conversion by 15%').")

    if word_count > 250:
        suggestions.append("Answer is long — aim to be concise and get to the point faster.")

    if content < 1.0:
        suggestions.append("Add specific tools, frameworks, or methodologies you used to show technical depth.")

    if not suggestions:
        suggestions.append("Solid, well-structured answer. Keep reinforcing with specific metrics/examples.")

    return {
        "score": score,
        "word_count": word_count,
        "filler_word_count": filler_count,
        "star_used": star,
        "question_type": question_type,
        "content_quality": content,
        "has_metrics": has_metrics,
        "mindset": _analyze_mindset(answer_lower),
        "suggestions": suggestions,
        "source": "offline",
    }


def _ai_score(question, answer):
    client = get_client()
    prompt = f"""
You are an expert interview coach. Evaluate this interview answer.

Question: {question}
Answer: {answer}

Score it out of 10 considering: clarity, confidence, structure (including use of
the STAR method), relevance to the question, and filler words.

Return ONLY JSON (no markdown fences) in this exact format:
{{"score": <number 1-10>, "suggestions": ["...", "..."], "strengths": ["...", "..."],
 "star_used": {{"situation": true/false, "task": true/false, "action": true/false, "result": true/false}}}}
"""
    response = client.chat.completions.create(
        model=model_name(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(raw)
    parsed["word_count"] = len(answer.split())
    parsed["filler_word_count"] = sum(answer.lower().count(f) for f in FILLER_WORDS)
    parsed["source"] = "gemini"
    return parsed


def evaluate_answer(question, answer):
    answer_lower = answer.lower().strip()
    mindset = _analyze_mindset(answer_lower)
    mindset_suggestions = _mindset_feedback(mindset)

    if is_configured():
        try:
            result = _ai_score(question, answer)
            result["mindset"] = mindset
            result["suggestions"] = (result.get("suggestions") or []) + mindset_suggestions
            return result
        except Exception:  # noqa: S110 - fall back to the offline heuristic scorer.
            pass

    result = _rule_based_score(question, answer)
    result["mindset"] = mindset
    result["suggestions"] = result.get("suggestions", []) + mindset_suggestions
    return result
