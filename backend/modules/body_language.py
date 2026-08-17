"""
Body Language Module
--------------------
Real-time posture & engagement analysis powered by MediaPipe.

``analyze_frame`` processes a single JPEG frame from the user's webcam in the
backend (Pose + Face Mesh with iris landmarks) and returns per-frame metrics:
face presence, eye contact, smile, blink, head stability, posture status,
shoulder tilt and apparent distance from the camera.

Per-answer or per-session frame histories are then aggregated and scored by
``analyze_body_language`` (ported/adapted from the previous implementation)
into a 0-10 body-language score plus interview-style suggestions.

All metrics are optional — the mock interview works without a camera.
"""
import json
import threading
from collections import Counter

try:
    import cv2
    import mediapipe as mp
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    mp = None
    np = None
    _CV2_AVAILABLE = False

# Reference ranges tuned for a typical web-cam interview session.
EYE_CONTACT_IDEAL_MIN = 60      # % of time looking toward the camera
SMILE_IDEAL_MIN = 15            # % of time smiling
HEAD_STEADY_IDEAL_MIN = 50      # % of time head roughly stable/centered
BLINK_IDEAL_RANGE = (10, 28)    # blinks per minute (healthy conversational range)
POSTURE_SHIFT_IDEAL_MAX = 12    # significant posture changes over the session

# Gaze is judged "on camera" when the iris sits near the horizontal/vertical
# center of the eye; 0.5 is dead-center. Deviation below this counts as contact.
GAZE_MAX_DEVIATION = 0.18
# EAR below this on both eyes counts as a blink (rough heuristic).
BLINK_EAR_THRESHOLD = 0.20
# Mouth-width / face-width ratio above this counts as a smile.
SMILE_RATIO_MIN = 0.45
# Too close / too far based on the eye-to-eye distance as a % of frame width.
EYE_DISTANCE_CLOSE_PCT = 35.0
EYE_DISTANCE_FAR_PCT = 8.0
# Spine angle (deg from vertical) beyond which we flag a lean.
LEAN_ANGLE_DEG = 12.0
# The pose is still "live" if its last frame is younger than this (ms).
POSTURE_STALE_MS = 2000

# Confidence model weights: how much each facial cue contributes to the
# per-frame confidence estimate (must sum to 1.0). Eye contact is the
# strongest signal, followed by head steadiness, posture and smiling.
CONFIDENCE_WEIGHTS = {"eye_contact": 0.40, "head_steady": 0.20, "posture": 0.20, "smile": 0.20}
# Aggregated confidence (0-10) thresholds for the level label.
CONFIDENCE_CONFIDENT_MIN = 8.0
CONFIDENCE_COMPOSED_MIN = 6.0

_LOCK = threading.Lock()
_FACE = None
_POSE = None


def _models():
    """Lazily construct (and share) MediaPipe solutions under a lock."""
    global _FACE, _POSE
    if not _CV2_AVAILABLE:
        return None, None
    if _FACE is None:
        _FACE = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )
        _POSE = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.5,
        )
    return _FACE, _POSE


# --------------------------------------------------------------------------
# Per-frame analysis
# --------------------------------------------------------------------------

def _pct(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, value))


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _face_metrics(landmarks, w, h):
    def pt(i):
        return (landmarks[i].x * w, landmarks[i].y * h)

    eye_contact, eye_contact_pct, smiling, blink, head_steady = False, 0.0, False, False, False

    # Gaze: iris position between the eye corners (0.5 = centered).
    deviations = []
    for outer, inner, iris, top, bottom in (
        (33, 133, 468, 159, 145),   # left eye
        (263, 362, 473, 386, 374),  # right eye
    ):
        o, i = pt(outer), pt(inner)
        eye_width = max(_dist(o, i), 1e-6)
        gaze_h = abs((pt(iris)[0] - o[0]) / eye_width - 0.5)
        t, b = pt(top), pt(bottom)
        eye_height = max(abs(b[1] - t[1]), 1e-6)
        gaze_v = abs((pt(iris)[1] - t[1]) / eye_height - 0.5)
        deviations.extend((gaze_h, gaze_v))
    deviation = sum(deviations) / len(deviations)
    eye_contact = deviation <= GAZE_MAX_DEVIATION
    eye_contact_pct = _pct(100.0 * (1.0 - min(1.0, deviation / 0.35)))

    # Blink: eye aspect ratio below threshold on both eyes.
    left_ear = _dist(pt(159), pt(145)) / max(_dist(pt(33), pt(133)), 1e-6)
    right_ear = _dist(pt(386), pt(374)) / max(_dist(pt(263), pt(362)), 1e-6)
    blink = left_ear < BLINK_EAR_THRESHOLD and right_ear < BLINK_EAR_THRESHOLD

    # Smile: mouth width relative to the face width.
    mouth_w = _dist(pt(61), pt(291))
    face_w = _dist(pt(234), pt(454))
    smiling = face_w > 0 and (mouth_w / face_w) > SMILE_RATIO_MIN

    # Head steady: nose tip near the horizontal center of the frame.
    head_steady = abs(landmarks[1].x - 0.5) < 0.15

    return {
        "face_present": True,
        "eye_contact": eye_contact,
        "eye_contact_pct": eye_contact_pct,
        "smiling": smiling,
        "blink": blink,
        "head_steady": head_steady,
        "face_width_pct": _pct(100.0 * _dist(pt(133), pt(362)) / w),
    }


def _pose_metrics(landmarks, w, h):
    def pt(i):
        return (landmarks[i].x * w, landmarks[i].y * h)

    nose = pt(0)
    ls, rs = pt(11), pt(12)
    lh, rh = pt(23), pt(24)
    shoulder_mid = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
    hip_mid = ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2)

    dx = shoulder_mid[0] - hip_mid[0]
    dy = max(abs(shoulder_mid[1] - hip_mid[1]), 1e-6)
    spine_angle = float(np.degrees(np.arctan(abs(dx) / dy)))

    posture = "good"
    if abs(shoulder_mid[0] - hip_mid[0]) / max(w, 1) > 0.02:
        posture = "leaning_left" if dx < 0 else "leaning_right"
    elif shoulder_mid[1] < hip_mid[1]:
        # Head dropped below the shoulders reads as slouching/head-down.
        if nose[1] > shoulder_mid[1] or spine_angle > LEAN_ANGLE_DEG:
            posture = "slouching"
    elif spine_angle > LEAN_ANGLE_DEG:
        posture = "leaning_left" if dx < 0 else "leaning_right"

    return {
        "pose_present": True,
        "posture": posture,
        "shoulder_angle": round(spine_angle, 1),
    }


def _frame_confidence(metrics):
    """
    Estimate 0-100 confidence from a single analyzed frame's facial cues.

    A weighted blend of eye contact, head steadiness, upright posture and
    smiling (see ``CONFIDENCE_WEIGHTS``). Returns 0.0 when no face is visible
    so the live gauge has something to show, and ``None`` for unprocessable
    frames (callers use that to drop the frame from aggregation).
    """
    if not metrics or not metrics.get("frame_ok"):
        return None
    if not metrics.get("face_present"):
        return 0.0
    eye = _pct(metrics.get("eye_contact_pct")) or 0.0
    w = CONFIDENCE_WEIGHTS
    score = w["eye_contact"] * (eye / 100.0)
    score += w["head_steady"] * (1.0 if metrics.get("head_steady") else 0.0)
    score += w["posture"] * (1.0 if metrics.get("posture") == "good" else 0.0)
    score += w["smile"] * (1.0 if metrics.get("smiling") else 0.0)
    return round(max(0.0, min(1.0, score)) * 100.0, 1)


def analyze_frame(jpeg_bytes, timestamp_ms=0):
    """
    Decode ``jpeg_bytes`` and return a dict of per-frame body-language metrics.

    Returns a dict with ``frame_ok=False`` (plus an ``errors`` list) when the
    frame cannot be decoded or processed. Never raises.
    """
    try:
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"frame_ok": False, "errors": ["cannot decode frame"]}
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return {"frame_ok": False, "errors": ["empty frame"]}
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        metrics = {
            "frame_ok": True,
            "ts_ms": timestamp_ms,
            "face_present": False,
            "eye_contact": False,
            "eye_contact_pct": 0.0,
            "smiling": False,
            "blink": False,
            "head_steady": False,
            "pose_present": False,
            "posture": "unknown",
            "shoulder_angle": None,
            "confidence": 0.0,
            "errors": [],
        }
        face_model, pose_model = _models()
        with _LOCK:
            face = face_model.process(rgb)
            pose = pose_model.process(rgb)
        if face.multi_face_landmarks:
            metrics.update(
                _face_metrics(face.multi_face_landmarks[0].landmark, w, h)
            )
        if pose.pose_landmarks:
            metrics.update(_pose_metrics(pose.pose_landmarks.landmark, w, h))
        metrics["confidence"] = _frame_confidence(metrics)
        return metrics
    except Exception as exc:  # pragma: no cover - defensive
        return {"frame_ok": False, "errors": [f"{type(exc).__name__}: {exc}"]}


# --------------------------------------------------------------------------
# Aggregation & scoring
# --------------------------------------------------------------------------

def aggregate_frames(frames):
    """
    Turn a list of per-frame metrics (from ``analyze_frame``) into the
    per-answer metric dict expected by ``analyze_body_language``.
    """
    frames = [f for f in frames or [] if f and f.get("frame_ok")]
    if not frames:
        return {}

    n = len(frames)

    def pct(key):
        return _pct(100.0 * sum(1 for f in frames if f.get(key)) / n)

    eye_pct = sum(f.get("eye_contact_pct") or 0.0 for f in frames) / n
    blinks = sum(1 for f in frames if f.get("blink"))

    # Time window: fall back to frame-count seconds when no timestamps.
    ts = [f.get("ts_ms") for f in frames if f.get("ts_ms")]
    if len(ts) >= 2 and max(ts) > min(ts):
        duration_seconds = (max(ts) - min(ts)) / 1000.0
    else:
        duration_seconds = n / 5.0  # ~5 fps sampling assumption

    posture_statuses = [f.get("posture") for f in frames]
    posture_breakdown = Counter(posture_statuses)
    # A posture "shift" = moving between different non-unknown statuses.
    shifts = sum(
        1
        for a, b in zip(posture_statuses, posture_statuses[1:], strict=False)
        if a != b and a != "unknown" and b != "unknown"
    )

    blink_rate = (
        round(blinks * 60.0 / duration_seconds, 1) if duration_seconds > 0 else None
    )

    # Confidence: average only over frames where a face was visible.
    conf_frames = [
        f.get("confidence")
        for f in frames
        if f.get("face_present") and isinstance(f.get("confidence"), int | float)
    ]
    confidence_pct = round(sum(conf_frames) / len(conf_frames), 1) if conf_frames else None

    return {
        "eye_contact_pct": round(eye_pct, 1),
        "face_present_pct": pct("face_present"),
        "smile_pct": pct("smiling"),
        "head_steady_pct": pct("head_steady"),
        "blink_rate_per_min": blink_rate,
        "posture_shift_count": shifts,
        "duration_seconds": round(duration_seconds, 1),
        "posture_breakdown": {k: v for k, v in posture_breakdown.items()},
        "dominant_posture": posture_statuses and Counter(posture_statuses).most_common(1)[0][0],
        "confidence_pct": confidence_pct,
    }


def analyze_body_language(metrics):
    """
    Score an aggregated metrics dict (see ``aggregate_frames``) into a
    ``0-10`` body-language score plus targeted suggestions.
    """
    metrics = metrics or {}
    eye = _pct(metrics.get("eye_contact_pct"))
    smile = _pct(metrics.get("smile_pct"))
    steady = _pct(metrics.get("head_steady_pct"))
    face = _pct(metrics.get("face_present_pct"))
    try:
        blink = float(metrics.get("blink_rate_per_min"))
    except (TypeError, ValueError):
        blink = None
    try:
        shifts = int(metrics.get("posture_shift_count", 0))
    except (TypeError, ValueError):
        shifts = 0

    score = 7.0
    notes = []

    # Eye contact / engagement
    ref = eye if eye is not None else face
    if ref is None:
        notes.append("No camera data received for this answer — eye contact not assessed.")
        score -= 1.0
    elif ref < EYE_CONTACT_IDEAL_MIN:
        notes.append(f"Eye contact was below target ({ref:.0f}% toward camera).")
        score -= min(2.0, (EYE_CONTACT_IDEAL_MIN - ref) / 40)

    # Smile / warmth
    if smile is not None:
        if smile < SMILE_IDEAL_MIN:
            notes.append("Smiling was rare — a measured smile builds rapport.")
            score -= 0.5
        elif smile >= 40:
            score += 0.3

    # Head stability
    if steady is not None and steady < HEAD_STEADY_IDEAL_MIN:
        notes.append("Head movement was frequent — keep it relaxed and steady.")
        score -= min(1.0, (HEAD_STEADY_IDEAL_MIN - steady) / 60)
    if shifts > POSTURE_SHIFT_IDEAL_MAX:
        notes.append("Frequent posture shifts can read as nervousness — settle into a position.")
        score -= 0.5

    # Posture breakdown (new in this phase)
    breakdown = metrics.get("posture_breakdown") or {}
    bad_posture = sum(v for k, v in breakdown.items() if k not in ("good", "unknown"))
    total_posture = sum(breakdown.values())
    if total_posture and bad_posture / total_posture > 0.3:
        worst = max(
            (k for k in breakdown if k not in ("good", "unknown")),
            key=lambda k: breakdown[k],
            default=None,
        )
        if worst:
            label = {"slouching": "slouching", "leaning_left": "leaning left",
                     "leaning_right": "leaning right", "too_close": "sitting too close",
                     "too_far": "sitting too far"}.get(worst, worst)
            notes.append(f"Posture flagged as '{label}' for much of the answer — sit upright.")
            score -= min(1.0, (bad_posture / total_posture) * 1.2)

    # Blink rate (nervousness proxy)
    if blink is not None:
        if blink > BLINK_IDEAL_RANGE[1] + 8:
            notes.append("Elevated blink rate detected — a sign of stress; pause and breathe.")
            score -= min(1.0, (blink - BLINK_IDEAL_RANGE[1]) / 40)
        elif blink < BLINK_IDEAL_RANGE[0]:
            notes.append("Very low blink rate — remember to blink naturally, not stare.")
            score -= 0.3

    score = max(1.0, min(10.0, round(score, 1)))

    # ---- Confidence: fused facial-cue estimate (0-10) --------------------
    conf_pct = metrics.get("confidence_pct")
    confidence, confidence_notes = None, []
    if conf_pct is None or face is None:
        confidence_notes.append("No face/camera data received for this answer — confidence not assessed.")
        level = "No camera data"
    else:
        adj = 0.0
        if face < 60:
            confidence_notes.append("Face was off-camera for much of the answer — stay visible to read as engaged.")
            adj -= 0.7
        if blink is not None:
            if BLINK_IDEAL_RANGE[0] <= blink <= BLINK_IDEAL_RANGE[1]:
                adj += 0.3
            elif blink > BLINK_IDEAL_RANGE[1] + 8:
                confidence_notes.append("Rapid blinking under pressure — slow down and breathe between points.")
                adj -= 0.6
        if shifts > POSTURE_SHIFT_IDEAL_MAX:
            confidence_notes.append("Settling into a stable posture will project more confidence.")
            adj -= 0.5
        confidence = round(max(1.0, min(10.0, float(conf_pct) / 10.0 + adj)), 1)
        if confidence >= CONFIDENCE_CONFIDENT_MIN:
            level = "Confident"
        elif confidence >= CONFIDENCE_COMPOSED_MIN:
            level = "Composed"
        else:
            level = "Nervous"

    suggestions = _suggestions(notes, score)
    if not suggestions:
        suggestions.append("Strong, relaxed non-verbal delivery — maintain this composure.")

    return {
        "score": score,
        "metrics": {
            "eye_contact_pct": eye,
            "smile_pct": smile,
            "head_steady_pct": steady,
            "face_present_pct": face,
            "blink_rate_per_min": blink,
            "posture_shift_count": shifts,
            "duration_seconds": metrics.get("duration_seconds"),
            "confidence_pct": conf_pct,
        },
        "confidence": {
            "score": confidence,
            "pct": round(float(conf_pct), 1) if conf_pct is not None else None,
            "level": level,
            "notes": confidence_notes,
        },
        "notes": notes,
        "suggestions": suggestions,
        "source": "heuristic",
    }


def _suggestions(notes, score):
    """Generate personalized, actionable coaching suggestions based on metrics."""
    if score >= 8:
        return ["Excellent body language — confident, engaged and calm. Keep this up!"]

    suggestions = []
    note_text = " ".join(notes).lower()

    # Eye contact suggestions (highest priority)
    if "eye contact" in note_text or "below target" in note_text:
        suggestions.append("Look directly into the camera lens, not the screen preview — this simulates eye contact with the interviewer.")
    elif score < 6:
        suggestions.append("Maintain steady eye contact with the camera (aim for 60%+ of the answer).")

    # Posture suggestions
    if "slouching" in note_text:
        suggestions.append("Sit upright with your back against the chair — imagine a string pulling the top of your head toward the ceiling.")
    elif "leaning" in note_text:
        suggestions.append("Center yourself in the frame and face the camera squarely — small shifts are fine, but settling reads as confident.")
    elif score < 6:
        suggestions.append("Sit upright and centered; only nod to emphasize key points.")

    # Smiling suggestions
    if "smile" in note_text:
        suggestions.append("Add a genuine smile when greeting and when making key points — it builds rapport and warmth.")

    # Nervousness / fidgeting
    if "shift" in note_text:
        suggestions.append("Pause silently before answering instead of fidgeting — a brief pause reads as thoughtfulness, not hesitation.")

    # Blink rate
    if "blink" in note_text:
        suggestions.append("Breathe slowly and deeply — this reduces rapid blinking and signals composure.")

    # Confidence-specific tips
    if "face" in note_text and "off-camera" in note_text:
        suggestions.append("Stay visible in the frame — leaning slightly toward the camera reads as engaged and confident.")

    # Fallback general tips (pick the most relevant)
    if not suggestions:
        general = [
            "Maintain steady eye contact with the camera (aim for 60%+ of the answer).",
            "Keep your head still and centered; only nod to emphasize key points.",
            "Pause silently before answering instead of fidgeting or shifting.",
        ]
        suggestions = general[:3]

    return suggestions[:3]


def summarize_metrics_json(metrics_list):
    """Serialize the per-answer metric history for a session report."""
    if not metrics_list:
        return []
    try:
        return [json.loads(m) if isinstance(m, str) else m for m in metrics_list]
    except (TypeError, ValueError):
        return metrics_list
