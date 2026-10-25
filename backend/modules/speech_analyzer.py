"""
Speech Analysis Module
------------------------
The frontend uses the browser's built-in Web Speech API to record and
transcribe the candidate's spoken answer (no paid speech-to-text API
needed). This module analyzes the resulting transcript + duration for:
  - pace (words per minute)
  - filler word usage
  - pause/confidence indicators
  - clarity score
"""

FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "actually",
                "sort of", "kind of", "i mean"]


def analyze_speech(transcript: str, duration_seconds: float):
    transcript = transcript or ""
    words = transcript.split()
    word_count = len(words)
    duration_seconds = max(duration_seconds or 1, 1)

    wpm = round((word_count / duration_seconds) * 60, 1)

    lower = transcript.lower()
    filler_hits = {f: lower.count(f) for f in FILLER_WORDS if lower.count(f) > 0}
    total_fillers = sum(filler_hits.values())
    filler_ratio = round(total_fillers / max(word_count, 1) * 100, 1)

    # Pace assessment
    if wpm < 100:
        pace_feedback = "Your pace is a bit slow — aim for a more natural, confident rhythm (120-160 WPM)."
    elif wpm > 170:
        pace_feedback = "You're speaking quite fast — slow down slightly so the interviewer can follow easily."
    else:
        pace_feedback = "Your pace is in a good conversational range."

    # Clarity score (0-10)
    clarity = 10
    clarity -= min(total_fillers * 0.5, 4)
    if wpm < 90 or wpm > 190:
        clarity -= 2
    if word_count < 20:
        clarity -= 2
    clarity = max(1, round(clarity, 1))

    suggestions = [pace_feedback]
    if total_fillers > 3:
        top_filler = max(filler_hits, key=filler_hits.get)
        suggestions.append(
            f"You used filler words {total_fillers} times (most common: '{top_filler}'). "
            "Practice pausing silently instead."
        )
    if word_count < 20:
        suggestions.append("Your response was brief — try elaborating with a specific example.")
    if clarity >= 8:
        suggestions.append("Great clarity and delivery overall!")

    return {
        "word_count": word_count,
        "duration_seconds": round(duration_seconds, 1),
        "words_per_minute": wpm,
        "filler_words_detected": filler_hits,
        "total_filler_words": total_fillers,
        "filler_ratio_percent": filler_ratio,
        "clarity_score": clarity,
        "suggestions": suggestions,
    }
