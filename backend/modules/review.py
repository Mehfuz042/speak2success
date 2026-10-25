"""
Review Module
--------------
Compiles an end-of-interview **Success Report** from the stored answers of a
mock session: per-round category breakdown, strengths, weaknesses, overall
verdict and a concrete action plan.
"""
import json

from .ai_config import chat_completion, is_configured

REVIEW_VERSION = 2
ROUND_ORDER = ["Managerial", "Technical", "Coding", "HR"]
DELIVERY_KEYS = (
    "eye_contact_pct",
    "smile_pct",
    "head_steady_pct",
    "face_present_pct",
    "blink_rate_per_min",
    "posture_shift_count",
    "confidence_pct",
)


def _category_breakdown(answers):
    per = {}
    for a in answers:
        cat = a.get("category", "Technical")
        per.setdefault(cat, []).append(a.get("score", 0))
    return {
        cat: round(sum(v) / len(v), 2)
        for cat, v in sorted(per.items(), key=lambda kv: ROUND_ORDER.index(kv[0]) if kv[0] in ROUND_ORDER else 99)
    }


def _strengths_weaknesses(rows):
    strengths, weaknesses = [], []
    answered = [row for row in rows if row.get("answered")]
    for row in answered:
        score = row.get("score") or 0
        label = f'{row.get("category", "Technical")}: "{row.get("question", "")[:80]}"'
        if score >= 8:
            detail = (row.get("strengths") or [""])[0]
            strengths.append(f"{label} — {detail}" if detail else label)
        elif score <= 5:
            detail = (row.get("improvements") or [""])[0]
            weaknesses.append(f"{label} — {detail}" if detail else label)

    # Always show some positives: if no answer reached 8/10, surface the
    # strongest answers' highlights instead of an empty "Strengths" card.
    if not strengths:
        ranked = sorted(
            (row for row in answered if row.get("strengths")),
            key=lambda row: row.get("score") or 0,
            reverse=True,
        )
        for row in ranked[:3]:
            detail = (row.get("strengths") or [""])[0]
            label = f'{row.get("category", "Technical")}: "{row.get("question", "")[:80]}"'
            strengths.append(f"{label} — {detail}" if detail else label)

    # Likewise never leave "Weaknesses" empty when answers exist.
    if not weaknesses and answered:
        lowest = min(answered, key=lambda row: row.get("score") or 0)
        detail = (lowest.get("improvements") or [""])[0]
        label = f'{lowest.get("category", "Technical")}: "{lowest.get("question", "")[:80]}"'
        weaknesses.append(f"{label} — {detail}" if detail else label)

    return strengths[:3], weaknesses[:3]


def _verdict(overall):
    if overall >= 8:
        return f"Strong interview. You are well prepared — {overall:.1f}/10 overall."
    if overall >= 6:
        return f"Solid foundation at {overall:.1f}/10 — polish a few areas to shine."
    return f"{overall:.1f}/10 overall — structured practice on core areas will move the needle."


def _score_verdict(score):
    if score is None:
        return "Not answered"
    if score >= 8:
        return "Strong answer"
    if score >= 6:
        return "Good answer — room to sharpen"
    if score >= 4:
        return "Needs work"
    return "Weak answer"


def _question_rows(session):
    """Flatten every question in the session, in interview order.

    ``question_number`` is numbered across the whole interview (1..N) so the
    report never repeats the same number, while ``round_question_number`` keeps
    the position inside its own round.
    """
    rows = []
    number = 0
    for round_def in (session or {}).get("rounds") or []:
        category = round_def.get("category") or "Technical"
        for round_number, question in enumerate(round_def.get("questions") or [], start=1):
            number += 1
            is_coding = question.get("type") == "coding"
            rows.append({
                "round_id": round_def.get("id") or "",
                "round_name": round_def.get("name") or f"{category} Round",
                "category": question.get("category") or category,
                "question_number": number,
                "round_question_number": round_number,
                "question": question.get("title") if is_coding else question.get("question", ""),
                "prompt": question.get("prompt"),
                "difficulty": question.get("difficulty", ""),
                "type": question.get("type", "theory"),
                "challenge_id": question.get("challenge_id"),
                "language": question.get("language"),
                "question_id": question.get("id"),
            })
    return rows


def _take_matching_answer(row, answers, used):
    """Find the stored answer belonging to a session question (or None if skipped)."""
    for answer in answers:
        if answer.get("id") in used:
            continue
        if row.get("type") == "coding":
            if row.get("challenge_id") and answer.get("challenge_id") == row["challenge_id"]:
                return answer
        answer_question = (answer.get("question") or "").strip()
        if answer_question and answer_question == (row.get("question") or "").strip():
            answer_round = answer.get("round_id")
            if not answer_round or not row.get("round_id") or answer_round == row["round_id"]:
                return answer
    # Fallback for older sessions whose round ids did not line up.
    for answer in answers:
        if answer.get("id") in used:
            continue
        if (answer.get("question") or "").strip() == (row.get("question") or "").strip():
            return answer
    return None


def _speech_summary(answer):
    speech = answer.get("speech")
    if not speech:
        return None
    return {
        "words_per_minute": speech.get("words_per_minute"),
        "clarity_score": speech.get("clarity_score"),
        "total_filler_words": speech.get("total_filler_words"),
        "filler_words_detected": speech.get("filler_words_detected") or {},
        "duration_seconds": speech.get("duration_seconds"),
        "word_count": speech.get("word_count"),
        "suggestions": speech.get("suggestions") or [],
    }


def _body_summary(answer):
    body = answer.get("body_language")
    if not body:
        return None
    confidence = body.get("confidence") or {}
    metrics = body.get("metrics") or {}
    if body.get("score") is None and confidence.get("score") is None and not metrics:
        return None
    return {
        "score": body.get("score"),
        "confidence": {
            "score": confidence.get("score"),
            "pct": confidence.get("pct"),
            "level": confidence.get("level") or "No camera data",
            "notes": confidence.get("notes") or [],
        },
        "metrics": metrics,
        "notes": body.get("notes") or [],
        "suggestions": body.get("suggestions") or [],
    }


def _answer_row(row, answer=None):
    """One report row per question — including questions the candidate skipped."""
    base = {
        "round_id": row.get("round_id"),
        "round_name": row.get("round_name"),
        "category": row.get("category", "Technical"),
        "question_number": row.get("question_number"),
        "round_question_number": row.get("round_question_number"),
        "question": row.get("question", ""),
        "prompt": row.get("prompt"),
        "difficulty": row.get("difficulty", ""),
        "type": row.get("type", "theory"),
        "challenge_id": row.get("challenge_id"),
        "language": row.get("language"),
        "question_id": row.get("question_id"),
        "answered": answer is not None,
        "answer_id": answer.get("id") if answer else None,
        "score": None,
        "verdict": "Not answered",
        "answer": None,
        "answer_preview": "",
        "strengths": [],
        "improvements": [
            "Rehearse a 60–90 second answer so you are ready for it next time."
        ],
        "suggestions": [],
        "top_suggestion": "",
        "speech": None,
        "body_language": None,
        "confidence": None,
        "star_used": None,
        "has_metrics": None,
        "word_count": None,
        "filler_word_count": None,
        "coding": None,
        "has_audio": False,
    }
    if not answer:
        return base

    feedback = answer.get("feedback") or {}
    score = round(float(answer.get("score") or 0), 1)
    suggestions = list(feedback.get("suggestions") or feedback.get("improvements") or [])
    strengths = list(feedback.get("strengths") or [])
    body = _body_summary(answer)
    confidence = (body or {}).get("confidence")
    speech = _speech_summary(answer)

    coding = None
    if row.get("type") == "coding" or answer.get("category") == "Coding":
        coding = {
            "passed": answer.get("passed"),
            "total": answer.get("total"),
            "score_percent": answer.get("score_percent"),
            "language": answer.get("language"),
            "code": answer.get("code"),
        }

    base.update({
        "score": score,
        "verdict": _score_verdict(score),
        "answer": answer.get("answer") or "",
        "answer_preview": (answer.get("answer") or "")[:280],
        "strengths": strengths,
        "improvements": suggestions or [
            "No specific improvement was generated for this answer."
        ],
        "suggestions": suggestions,
        "top_suggestion": suggestions[0] if suggestions else "",
        "speech": speech,
        "body_language": body,
        "confidence": confidence,
        "star_used": feedback.get("star_used"),
        "has_metrics": feedback.get("has_metrics"),
        "word_count": feedback.get("word_count") or answer.get("word_count"),
        "filler_word_count": feedback.get("filler_word_count"),
        "coding": coding,
        "has_audio": bool(answer.get("audio_file")),
    })
    return base


def _answer_feedback(answers, session=None):
    """Build question-by-question feedback for *every* question in the session.

    Falling back to the raw answer list keeps this helper useful for callers
    that only have answers (e.g. older cached reports and unit tests).
    """
    answers = list(answers or [])
    session_questions = _question_rows(session)

    if not session_questions:
        rows = []
        for index, answer in enumerate(answers, start=1):
            row = {
                "round_id": answer.get("round_id") or "",
                "round_name": f'{answer.get("category") or "Technical"} Round',
                "category": answer.get("category", "Technical"),
                "question_number": index,
                "question": answer.get("question", ""),
                "prompt": None,
                "difficulty": answer.get("difficulty", ""),
                "type": answer.get("type", "theory"),
                "challenge_id": answer.get("challenge_id"),
                "language": answer.get("language"),
                "question_id": None,
            }
            rows.append(_answer_row(row, answer))
        return rows

    used = set()
    report_rows = []
    for row in session_questions:
        answer = _take_matching_answer(row, answers, used)
        if answer:
            used.add(answer.get("id"))
        report_rows.append(_answer_row(row, answer))

    # Keep any answers that were submitted outside the generated question list
    # (e.g. a session created before a schema change) so nothing is lost.
    for answer in answers:
        if answer.get("id") in used:
            continue
        extra = {
            "round_id": answer.get("round_id") or "",
            "round_name": f'{answer.get("category") or "Technical"} Round',
            "category": answer.get("category", "Technical"),
            "question_number": None,
            "question": answer.get("question", ""),
            "prompt": None,
            "difficulty": answer.get("difficulty", ""),
            "type": answer.get("type", "theory"),
            "challenge_id": answer.get("challenge_id"),
            "language": answer.get("language"),
            "question_id": None,
        }
        report_rows.append(_answer_row(extra, answer))
    return report_rows


def _action_plan(breakdown, rows=None, body_language=None, unanswered=0):
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
    confidence = (body_language or {}).get("confidence") or {}
    if confidence.get("score") is not None and confidence["score"] < 6:
        plan.append(
            "Work on confident delivery: sit upright, keep your gaze on the camera, and pause instead of "
            "filling silence. Record a 60-second answer and review your eye contact and posture."
        )
    elif confidence.get("score") is not None and confidence["score"] < 8:
        plan.append(
            "Sharpen your on-camera presence — aim for 70%+ eye contact and a relaxed, steady posture so your "
            "confidence score crosses 8/10."
        )
    if unanswered:
        plan.append(
            f"Re-attempt the {unanswered} question{'s' if unanswered != 1 else ''} you skipped — a complete "
            "interview is part of the assessment."
        )
    if not plan:
        plan.append("Reinforce your strengths with harder questions at a faster pace.")
    return plan[:4]


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
                suggestions.append(
                    "Show more learning language — mention courses, self-study, or "
                    "skills you developed over time."
                )
            elif trait_id == "ownership":
                suggestions.append(
                    "Use more ownership language — say 'I led', 'I decided', 'I ensured' "
                    "instead of passive phrasing."
                )
            elif trait_id == "problem_solving":
                suggestions.append(
                    "Describe your problem-solving process step by step — analysis, "
                    "options, decision, result."
                )
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
            ("blink_rate_per_min", b.get("metrics", {}).get("blink_rate_per_min")),
            ("posture_shift_count", b.get("metrics", {}).get("posture_shift_count")),
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
        (b.get("confidence") or {}).get("score")
        for b in bodies
        if (b.get("confidence") or {}).get("score") is not None
    ]
    confidence_pcts = [
        (b.get("confidence") or {}).get("pct")
        for b in bodies
        if (b.get("confidence") or {}).get("pct") is not None
    ]
    levels = [
        (b.get("confidence") or {}).get("level")
        for b in bodies
        if (b.get("confidence") or {}).get("score") is not None
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
            "confident_answers": levels.count("Confident"),
            "composed_answers": levels.count("Composed"),
            "nervous_answers": levels.count("Nervous"),
            "answers_assessed": len(confidence_scores),
        }

    return {
        "score": _avg(scores),
        "covered_answers": len(bodies),
        "confidence": confidence,
        "metrics": {
            label: round(sum(v) / len(v), 1) if v else None
            for label, v in per_label.items()
        },
        "suggestions": top,
    }


def _rule_based_review(answers, role, session=None):
    breakdown = _category_breakdown(answers)
    overall = round(sum(breakdown.values()) / len(breakdown), 2) if breakdown else 0.0
    rows = _answer_feedback(answers, session)
    strengths, weaknesses = _strengths_weaknesses(rows)
    answered = sum(1 for r in rows if r.get("answered"))
    total = len(rows)
    body_language = _body_language_summary(answers)

    suggestions = []
    for cat, avg in breakdown.items():
        if avg < 6:
            suggestions.append(
                f"Your weakest area is {cat} ({avg:.1f}/10) — practise more with concrete, metric-driven examples."
            )
    if not suggestions:
        suggestions.append("Consistent performance across categories — push with harder questions.")

    return {
        "review_version": REVIEW_VERSION,
        "role": role,
        "overall_score": overall,
        "questions_total": total,
        "questions_answered": answered,
        "questions_skipped": total - answered,
        "category_breakdown": breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "verdict": _verdict(overall),
        "suggestions": suggestions,
        "answer_feedback": rows,
        "action_plan": _action_plan(
            breakdown, rows, body_language, unanswered=total - answered
        ),
        "body_language": body_language,
        "confidence": (body_language or {}).get("confidence"),
        "mindset": _mindset_summary(answers),
        "source": "offline",
    }


def _ai_review(answers, role, session=None):
    rows = _answer_feedback(answers, session)
    body_language = _body_language_summary(answers)
    total = len(rows)
    answered = sum(1 for r in rows if r.get("answered"))

    lines = []
    for row in rows:
        if not row.get("answered"):
            lines.append(
                f"- [{row.get('category')}] Q: {row.get('question', '')[:160]} — NOT ANSWERED (skipped)"
            )
            continue
        confidence = row.get("confidence") or {}
        speech = row.get("speech") or {}
        body = row.get("body_language") or {}
        delivery = []
        if confidence.get("score") is not None:
            delivery.append(
                f"confidence {confidence['score']}/10 ({confidence.get('level')})"
            )
        if body.get("score") is not None:
            delivery.append(f"body language {body['score']}/10")
        metrics = body.get("metrics") or {}
        if metrics.get("eye_contact_pct") is not None:
            delivery.append(f"eye contact {metrics['eye_contact_pct']:.0f}%")
        if speech.get("words_per_minute") is not None:
            delivery.append(f"pace {speech['words_per_minute']:.0f} WPM")
        delivery_text = f" | {', '.join(delivery)}" if delivery else " | no camera/speech data"
        lines.append(
            f"- [{row.get('category')}] (score {row.get('score', 0)}/10{delivery_text}) "
            f"Q: {row.get('question', '')[:160]} A: {(row.get('answer') or '')[:300]}"
        )
    summary = "\n".join(lines)

    prompt = f"""
You are a senior interview coach. Review this mock interview for a "{role}" candidate.

The candidate answered {answered} of {total} questions. Per-question data below includes
answer scores, body-language scores, confidence scores and speech pace.

Answers:
{summary}

Return ONLY JSON (no markdown fences):
{{"overall_score": <1-10>, "category_breakdown": {{"Managerial": <x>, "Technical": <x>, "Coding": <x>, "HR": <x>}},
 "strengths": ["..."], "weaknesses": ["..."],
 "verdict": "<2-3 sentences that mention both answer quality and on-camera confidence>",
 "suggestions": ["..."],
 "action_plan": ["3-4 concrete practice steps"]}}
"""
    response = chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    parsed = json.loads(raw)
    parsed["review_version"] = REVIEW_VERSION
    parsed["role"] = role
    parsed["questions_total"] = total
    parsed["questions_answered"] = answered
    parsed["questions_skipped"] = total - answered
    parsed["answer_feedback"] = rows
    parsed["action_plan"] = parsed.get("action_plan") or _action_plan(
        parsed.get("category_breakdown", {}), rows, body_language, total - answered
    )
    parsed["body_language"] = body_language
    parsed["confidence"] = (body_language or {}).get("confidence")
    parsed["mindset"] = _mindset_summary(answers)
    parsed["source"] = "gemini"
    return parsed


def build_review(answers, role="Software Engineer", session=None):
    """Build the Success Report; uses Gemini when available, else heuristics."""
    if is_configured() and answers:
        try:
            return _ai_review(answers, role, session=session)
        except Exception:  # noqa: S110 - fall back to the rule-based review.
            pass
    return _rule_based_review(answers, role, session=session)
