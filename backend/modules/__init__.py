"""Speak2Success feature modules.

    ai_config          Gemini client wiring (OpenAI-compatible endpoint)
    resume_parser      PDF/TXT -> skills, roles, experience
    question_generator Managerial / Technical / HR questions (+ language theory)
    coding_challenges  13-challenge bank + multi-language subprocess runner
    speech_analyzer    WPM, filler words, clarity
    feedback_engine    answer scoring (Gemini or STAR-aware heuristics)
    review             end-of-interview Success Report
    storage            in-memory session store
"""
