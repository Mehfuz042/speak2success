"""
Review Module
--------------
Compiles an end-of-interview **Success Report** from the stored answers of a
mock session: per-round category breakdown, strengths, weaknesses, overall
verdict and a concrete action plan.
"""
import json

from .ai_config import get_client, is_configured, model_name

ROUND_ORDER = ["Managerial", "Technical", "Coding", "HR"]


def _category_breakdown(answers):
    per = {}
    for a in answers:
        cat = a.get("category", "Technical")
        per.setdefault(cat, []).append(a.get("score", 0))
    return {
        cat: round(sum(v) / len(v), 2)
        for cat, v in sorted(per.items(), key=lambda kv: ROUND_ORDER.index(kv[0]) if kv[0] in ROUND_ORDER else 99)
    }


def _strengths_weaknesses(answers):
    strengths, weaknesses = [], []
    for a in answers:
        score = a.get("score", 0)
        label = f'{a.get("category", "Technical")}: "{a.get("question", "")[:90]}..."'
        if score >= 8:
            strengths.append(label)
        elif score <= 5:
            weaknesses.append(label)
    return strengths[:3], weaknesses[:3]


def _verdict(overall):
    if overall >= 8:
        return f"Strong interview. You are well prepared — {overall:.1f}/10 overall."
    if overall >= 6:
        return f"Solid foundation at {overall:.1f}/10 — polish a few areas to shine."
    return f"{overall:.1f}/10 overall — structured practice on core areas will move the needle."


def _answer_feedback(answers):
    rows = []
    for a in answers:
        fb = a.get("feedback") or {}
        suggestions = fb.get("suggestions") or []
        rows.append({
            "question": a.get("question", ""),
            "category": a.get("category", "Technical"),
            "difficulty": a.get("difficulty", ""),
            "type": a.get("type", "theory"),
            "answer_id": a.get("id"),
            "score": round(float(a.get("score") or 0), 1),
            "top_suggestion": suggestions[0] if suggestions else "",
            "code": a.get("code"),
            "passed": a.get("passed"),
            "total": a.get("total"),
            "speech": (a.get("speech") or {}).get("words_per_minute"),
            "has_audio": bool(a.get("audio_file")),
        })
    return rows


def _action_plan(breakdown):
    plan = []
    if breakdown:
        weakest = min(breakdown, key=breakdown.get)
        if breakdown[weakest] < 7:
            plan.append(
                f"Raise your {weakest} performance (currently {breakdown[weakest]:.1f}/10) — drill focused "
                f"questions and rehearse structured, example-driven answers."
            )
    coding = breakdown.get("Coding")
    if coding is not None and coding < 8:
        plan.append("Practice more coding problems at your target difficulty and review time/space complexity.")
    if not plan:
        plan.append("Reinforce your strengths with harder questions at a faster pace.")
    return plan[:3]


def _mindset_summary(answers):
    """Aggregate per-answer mindset analysis into a session-level profile."""
    mindsets = [a.get("feedback", {}).get("mindset") for a in answers if a.get("feedback", {}).get("mindset")]
    if not mindsets:
        return None

    # Aggregate trait scores across all answers
    all_traits = {}
    for m in mindsets:
        for trait_id, trait in m.get("traits", {}).items():
            all_traits.setdefault(trait_id, {"label": trait["label"], "scores": []})
            all_traits[trait_id]["scores"].append(trait["score"])

    traits = {}
    for trait_id, data in all_traits.items():
        scores = data["scores"]
        avg_score = round(sum(scores) / len(scores), 1)
        traits[trait_id] = {
            "label": data["label"],
            "score": avg_score,
            "answers_analyzed": len(scores),
        }

    sorted_traits = sorted(traits.items(), key=lambda x: x[1]["score"], reverse=True)
    dominant = [t[1]["label"] for t in sorted_traits[:3] if t[1]["score"] >= 7.0]
    growth_areas = [t[1]["label"] for t in sorted_traits if t[1]["score"] < 5.0]

    overall_scores = [m.get("overall_score", 5.0) for m in mindsets]
    overall = round(sum(overall_scores) / len(overall_scores), 1)

    # Generate mindset-specific suggestions
    suggestions = []
    for trait_id, trait in sorted_traits:
        if trait["score"] < 4.0:
            if trait_id == "growth_mindset":
                suggestions.append("Show more learning language — mention courses, self-study, or skills you developed over time.")
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

    return {
        "overall_score": overall,
        "traits": traits,
        "dominant_traits": dominant,
        "growth_areas": growth_areas,
        "suggestions": suggestions[:5],
    }


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def _body_language_summary(answers):
    """Aggregate per-answer body-language metrics into a session-level summary."""
    bodies = [a.get("body_language") for a in answers if a.get("body_language")]
    if not bodies:
        return None

    scores = [b.get("score") for b in bodies if b.get("score") is not None]
    breakdowns = []
    for b in bodies:
        for label, value in (
            ("eye_contact_pct", b.get("metrics", {}).get("eye_contact_pct")),
            ("smile_pct", b.get("metrics", {}).get("smile_pct")),
            ("head_steady_pct", b.get("metrics", {}).get("head_steady_pct")),
            ("face_present_pct", b.get("metrics", {}).get("face_present_pct")),
        ):
            breakdowns.append((label, value))
    per_label = {}
    for label, value in breakdowns:
        if value is not None:
            per_label.setdefault(label, []).append(value)

    suggestions = []
    for b in bodies:
        suggestions.extend(b.get("suggestions") or [])
    # Keep the most common suggestion, de-duplicated.
    seen = set()
    top = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            top.append(s)
        if len(top) >= 3:
            break

    confidence_scores = [
        b.get("confidence", {}).get("score")
        for b in bodies
        if b.get("confidence", {}).get("score") is not None
    ]
    confidence_pcts = [
        b.get("confidence", {}).get("pct")
        for b in bodies
        if b.get("confidence", {}).get("pct") is not None
    ]
    confidence = None
    if confidence_scores:
        avg_conf = round(sum(confidence_scores) / len(confidence_scores), 1)
        confidence = {
            "score": avg_conf,
            "pct": round(sum(confidence_pcts) / len(confidence_pcts), 1) if confidence_pcts else None,
            "level": (
                "Confident"
                if avg_conf >= 8.0
                else "Composed"
                if avg_conf >= 6.0
                else "Nervous"
            ),
        }

    return {
        "score": _avg(scores),
        "covered_answers": len(bodies),
        "metrics": {
            label: round(sum(v) / len(v), 1) if v else None
            for label, v in per_label.items()
        },
        "confidence": confidence,
        "suggestions": top,
    }


def _rule_based_review(answers, role):
    breakdown = _category_breakdown(answers)
    overall = round(sum(breakdown.values()) / len(breakdown), 2) if breakdown else 0.0
    strengths, weaknesses = _strengths_weaknesses(answers)

    suggestions = []
    for cat, avg in breakdown.items():
        if avg < 6:
            suggestions.append(
                f"Your weakest area is {cat} ({avg:.1f}/10) — practise more with concrete, metric-driven examples."
            )
    if not suggestions:
        suggestions.append("Consistent performance across categories — push with harder questions.")

    return {
        "role": role,
        "overall_score": overall,
        "category_breakdown": breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "verdict": _verdict(overall),
        "suggestions": suggestions,
        "answer_feedback": _answer_feedback(answers),
        "action_plan": _action_plan(breakdown),
        "body_language": _body_language_summary(answers),
        "mindset": _mindset_summary(answers),
        "source": "offline",
    }


def _ai_review(answers, role):
    client = get_client()
    summary = "\n".join(
        f"- [{a.get('category', 'Technical')}] (score {a.get('score', 0)}/10) "
        f"Q: {a.get('question', '')[:160]} A: {a.get('answer', '')[:300]}"
        for a in answers
    )
    prompt = f"""
You are a senior interview coach. Review this mock interview for a "{role}" candidate.

Answers:
{summary}

Return ONLY JSON (no markdown fences):
{{"overall_score": <1-10>, "category_breakdown": {{"Managerial": <x>, "Technical": <x>, "Coding": <x>, "HR": <x>}},
 "strengths": ["..."], "weaknesses": ["..."],
 "verdict": "<2-3 sentences>", "suggestions": ["..."],
 "action_plan": ["3 concrete practice steps"]}}
"""
    response = client.chat.completions.create(
        model=model_name(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    parsed = json.loads(raw)
    parsed["role"] = role
    parsed["answer_feedback"] = _answer_feedback(answers)
    parsed["action_plan"] = parsed.get("action_plan") or _action_plan(parsed.get("category_breakdown", {}))
    parsed["body_language"] = _body_language_summary(answers)
    parsed["mindset"] = _mindset_summary(answers)
    parsed["source"] = "gemini"
    return parsed


def build_review(answers, role="Software Engineer"):
    """Build the Success Report; uses Gemini when available, else heuristics."""
    if is_configured() and answers:
        try:
            return _ai_review(answers, role)
        except Exception:  # noqa: S110 - fall back to the rule-based review.
            pass
    return _rule_based_review(answers, role)
