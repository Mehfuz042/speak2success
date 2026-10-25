/**
 * Live AI coach — runs MediaPipe Tasks Vision entirely in the browser.
 *
 * The camera frames never leave the device. For every sampled frame we compute
 * the same signals the backend used to produce server-side:
 *   - face presence, eye contact, smile, blink
 *   - head steadiness (facial transformation yaw/pitch/roll)
 *   - posture, shoulder tilt and framing distance (pose landmarks)
 *   - a fused 0-100 confidence score
 *
 * Per-answer metrics are aggregated with the same keys the backend scoring
 * module (`analyze_body_language`) expects, so the report keeps working.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  FaceLandmarker,
  FilesetResolver,
  PoseLandmarker,
} from '@mediapipe/tasks-vision'
import { temporalHeadSteady } from '../lib/headSteadiness'

const FPS = 5
const POSE_MIN_INTERVAL_MS = 350
const BLENDSHAPE_SMILE_MIN = 0.3
const BLENDSHAPE_BLINK_MIN = 0.5
const GAZE_ON_CAMERA_MAX = 0.55
const CONFIDENCE_WEIGHTS = { eye_contact: 0.45, head_steady: 0.25, posture: 0.2, smile: 0.1 }
const CONFIDENCE_SMOOTHING = 0.3
// Posture framing thresholds, in normalised image coordinates.
const SHOULDER_TOO_CLOSE = 0.6
const SHOULDER_TOO_FAR = 0.12

const assetBase = import.meta.env.BASE_URL || '/'
const modelPath = (file) => `${assetBase}mediapipe/models/${file}`
const wasmPath = () => `${assetBase}mediapipe/wasm`

let modelsPromise = null

async function createFaceLandmarker(fileset, delegate) {
  return FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: modelPath('face_landmarker.task'), delegate },
    runningMode: 'VIDEO',
    numFaces: 1,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
    minFaceDetectionConfidence: 0.5,
    minFacePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  })
}

async function createPoseLandmarker(fileset, delegate) {
  return PoseLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: modelPath('pose_landmarker_lite.task'), delegate },
    runningMode: 'VIDEO',
    numPoses: 1,
    minPoseDetectionConfidence: 0.5,
    minPosePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  })
}

async function createWithFallback(factory, fileset) {
  try {
    return await factory(fileset, 'GPU')
  } catch {
    // Some GPUs/drivers reject the WebGL delegate — CPU is slower but reliable.
    return factory(fileset, 'CPU')
  }
}

/** Load both models once per page and reuse them for every question. */
function loadModels() {
  if (!modelsPromise) {
    modelsPromise = (async () => {
      const fileset = await FilesetResolver.forVisionTasks(wasmPath())
      const [face, pose] = await Promise.all([
        createWithFallback(createFaceLandmarker, fileset),
        createWithFallback(createPoseLandmarker, fileset),
      ])
      return { face, pose }
    })().catch((error) => {
      modelsPromise = null
      throw error
    })
  }
  return modelsPromise
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const clamp = (value, low, high) => Math.max(low, Math.min(high, value))
const round1 = (value) => Math.round(value * 10) / 10

function blendshapeMap(result) {
  const categories = result?.faceBlendshapes?.[0]?.categories ?? []
  const map = {}
  for (const item of categories) map[item.categoryName] = item.score
  return map
}

/** Extract yaw/pitch/roll (degrees) from MediaPipe's column-major matrix. */
function headAngles(matrixData) {
  if (!matrixData || matrixData.length < 16) return { yaw: null, pitch: null, roll: null }
  const m20 = matrixData[2]
  const m21 = matrixData[6]
  const m22 = matrixData[10]
  const m10 = matrixData[1]
  const m00 = matrixData[0]
  const toDeg = 180 / Math.PI
  return {
    yaw: round1(Math.atan2(m20, m22) * toDeg),
    pitch: round1(Math.asin(clamp(-m21, -1, 1)) * toDeg),
    roll: round1(Math.atan2(m10, m00) * toDeg),
  }
}

/** Pose-based posture / framing analysis (works even if hips are out of frame). */
function postureFromPose(landmarks) {
  const empty = {
    pose_present: false,
    posture: 'unknown',
    shoulder_angle: null,
    shoulder_width_pct: null,
  }
  if (!landmarks || landmarks.length < 25) return empty

  const leftShoulder = landmarks[11]
  const rightShoulder = landmarks[12]
  const leftHip = landmarks[23]
  const rightHip = landmarks[24]
  const nose = landmarks[0]
  const visible = (point) => (point?.visibility ?? 1) >= 0.5

  if (!leftShoulder || !rightShoulder || !visible(leftShoulder) || !visible(rightShoulder)) {
    return empty
  }

  const shoulderWidth = Math.hypot(
    leftShoulder.x - rightShoulder.x,
    leftShoulder.y - rightShoulder.y,
  )
  if (shoulderWidth < 0.02) return empty

  const shoulderMidX = (leftShoulder.x + rightShoulder.x) / 2
  const shoulderMidY = (leftShoulder.y + rightShoulder.y) / 2
  const tilt = Math.abs(leftShoulder.y - rightShoulder.y) / shoulderWidth
  let posture = 'good'

  if (shoulderWidth > SHOULDER_TOO_CLOSE) {
    posture = 'too_close'
  } else if (shoulderWidth < SHOULDER_TOO_FAR) {
    posture = 'too_far'
  } else if (Math.abs(shoulderMidX - 0.5) > 0.22) {
    posture = shoulderMidX < 0.5 ? 'leaning_left' : 'leaning_right'
  } else if (tilt > 0.18) {
    posture = leftShoulder.y > rightShoulder.y ? 'leaning_left' : 'leaning_right'
  } else if (nose && Math.abs(nose.x - shoulderMidX) / shoulderWidth > 0.45) {
    posture = nose.x < shoulderMidX ? 'leaning_left' : 'leaning_right'
  } else if (visible(leftHip) && visible(rightHip)) {
    const hipMidX = (leftHip.x + rightHip.x) / 2
    const hipMidY = (leftHip.y + rightHip.y) / 2
    const dx = shoulderMidX - hipMidX
    const dy = Math.max(Math.abs(shoulderMidY - hipMidY), 1e-6)
    if (Math.abs(dx) > 0.06 || Math.abs(Math.atan2(dx, dy)) > 0.24) {
      posture = dx < 0 ? 'leaning_left' : 'leaning_right'
    }
  }

  return {
    pose_present: true,
    posture,
    shoulder_angle: round1(tilt * 45),
    shoulder_width_pct: round1(shoulderWidth * 100),
  }
}

function faceMetrics(result, headHistory) {
  const hasFace = Boolean(result?.faceLandmarks?.length)
  if (!hasFace) {
    // Keep the window; the time-based prune handles longer absences without
    // penalising a single dropped detection.
    return {
      face_present: false,
      eye_contact: false,
      eye_contact_pct: 0,
      smiling: false,
      blink: false,
      head_steady: false,
      yaw: null,
      pitch: null,
      roll: null,
      gaze_deviation: null,
      face_width_pct: null,
    }
  }

  const shapes = blendshapeMap(result)
  const gazeDeviation = (
    (shapes.eyeLookInLeft ?? 0) + (shapes.eyeLookOutLeft ?? 0) +
    (shapes.eyeLookUpLeft ?? 0) + (shapes.eyeLookDownLeft ?? 0) +
    (shapes.eyeLookInRight ?? 0) + (shapes.eyeLookOutRight ?? 0) +
    (shapes.eyeLookUpRight ?? 0) + (shapes.eyeLookDownRight ?? 0)
  ) / 8

  const angles = headAngles(result.facialTransformationMatrixes?.[0]?.data)
  const headFacing = (
    angles.yaw != null &&
    Math.abs(angles.yaw) <= 20 &&
    Math.abs(angles.pitch) <= 16
  )
  const gazeCentered = gazeDeviation <= GAZE_ON_CAMERA_MAX
  const eyeContact = headFacing && gazeCentered

  // 100 when relaxed and looking at the lens, falling off with gaze/head drift.
  const gazePct = 100 * (1 - clamp(gazeDeviation / 0.85, 0, 1))
  const headPenalty = angles.yaw == null
    ? 30
    : clamp((Math.abs(angles.yaw) - 10) / 22, 0, 1) * 45 +
      clamp((Math.abs(angles.pitch) - 8) / 22, 0, 1) * 35
  const eyeContactPct = Math.round(clamp(gazePct - headPenalty, 0, 100) * 10) / 10

  const smile = ((shapes.mouthSmileLeft ?? 0) + (shapes.mouthSmileRight ?? 0)) / 2
  const blink = (
    (shapes.eyeBlinkLeft ?? 0) + (shapes.eyeBlinkRight ?? 0)
  ) / 2 >= BLENDSHAPE_BLINK_MIN

  const headSteady = temporalHeadSteady(angles, headHistory)

  // Face width as a % of frame width (landmarks 234 and 454 are cheek edges).
  const landmarks = result.faceLandmarks[0]
  let faceWidthPct = null
  if (landmarks?.[234] && landmarks?.[454]) {
    const dx = landmarks[234].x - landmarks[454].x
    const dy = landmarks[234].y - landmarks[454].y
    faceWidthPct = round1(Math.hypot(dx, dy) * 100)
  }

  return {
    face_present: true,
    eye_contact: eyeContact,
    eye_contact_pct: eyeContactPct,
    smiling: smile >= BLENDSHAPE_SMILE_MIN,
    blink,
    head_steady: headSteady,
    yaw: angles.yaw,
    pitch: angles.pitch,
    roll: angles.roll,
    gaze_deviation: round1(gazeDeviation * 1000) / 1000,
    face_width_pct: faceWidthPct,
  }
}

function fuseConfidence(metrics) {
  if (!metrics.frame_ok) return null
  if (!metrics.face_present) return 0

  const weights = { ...CONFIDENCE_WEIGHTS }
  const postureKnown = metrics.pose_present && metrics.posture !== 'unknown'
  if (!postureKnown) {
    // Don't punish a candidate whose shoulders are out of frame.
    weights.eye_contact += weights.posture / 2
    weights.head_steady += weights.posture / 2
    weights.posture = 0
  }

  let score = 0
  score += weights.eye_contact * (clamp(metrics.eye_contact_pct ?? 0, 0, 100) / 100)
  score += weights.head_steady * (metrics.head_steady ? 1 : 0)
  score += weights.posture * (postureKnown && metrics.posture === 'good' ? 1 : 0)
  score += weights.smile * (metrics.smiling ? 1 : 0)
  return round1(clamp(score, 0, 1) * 100)
}

// ---------------------------------------------------------------------------
// Aggregation (per answer) — same shape as the backend's aggregate_frames.
// ---------------------------------------------------------------------------

function avg(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
}

export function aggregateFrames(frames) {
  const valid = (frames || []).filter((frame) => frame && frame.frame_ok)
  if (!valid.length) return {}

  const n = valid.length
  const pct = (key) => Math.round((100 * valid.filter((f) => f[key]).length) / n * 10) / 10
  const timestamps = valid.map((f) => f.ts_ms).filter((ts) => ts != null)
  const duration = timestamps.length >= 2 && Math.max(...timestamps) > Math.min(...timestamps)
    ? (Math.max(...timestamps) - Math.min(...timestamps)) / 1000
    : n / FPS

  const statuses = valid.map((f) => f.posture ?? 'unknown')
  const shifts = statuses.reduce((acc, status, index) => {
    const previous = statuses[index - 1]
    return previous && status !== previous && status !== 'unknown' && previous !== 'unknown'
      ? acc + 1
      : acc
  }, 0)
  const breakdown = {}
  statuses.forEach((status) => {
    breakdown[status] = (breakdown[status] ?? 0) + 1
  })

  // Count blink *events* (rising edges), not frames.
  let blinkEvents = 0
  let wasBlinking = false
  for (const frame of valid) {
    if (frame.blink && !wasBlinking) blinkEvents += 1
    wasBlinking = Boolean(frame.blink)
  }

  const confidenceFrames = valid
    .filter((f) => f.face_present && typeof f.confidence === 'number')
    .map((f) => f.confidence)

  return {
    eye_contact_pct: Math.round(avg(valid.map((f) => f.eye_contact_pct ?? 0)) * 10) / 10,
    face_present_pct: pct('face_present'),
    smile_pct: pct('smiling'),
    head_steady_pct: pct('head_steady'),
    blink_rate_per_min: duration > 0
      ? Math.round((blinkEvents * 60) / duration * 10) / 10
      : null,
    posture_shift_count: shifts,
    duration_seconds: Math.round(duration * 10) / 10,
    posture_breakdown: breakdown,
    dominant_posture: statuses.length
      ? Object.entries(breakdown).sort((a, b) => b[1] - a[1])[0][0]
      : 'unknown',
    confidence_pct: confidenceFrames.length
      ? Math.round(avg(confidenceFrames) * 10) / 10
      : null,
    frames_analyzed: n,
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export default function useBodyCoach() {
  const [status, setStatus] = useState('idle') // idle | connecting | live | error
  const [latest, setLatest] = useState(null)
  const [error, setError] = useState(null)
  const [frames, setFrames] = useState(0)

  const videoRef = useRef(null)
  const modelsRef = useRef(null)
  const timerRef = useRef(null)
  const historyRef = useRef([])
  const startTsRef = useRef(0)
  const lastTimestampRef = useRef(0)
  const lastPoseRef = useRef({ at: 0, metrics: postureFromPose(null) })
  const headHistoryRef = useRef([])
  const smoothedConfidenceRef = useRef(null)
  const busyRef = useRef(false)
  const statusRef = useRef('idle')

  const setCoachStatus = (next) => {
    statusRef.current = next
    setStatus(next)
  }

  const processFrame = useCallback(() => {
    const video = videoRef.current
    const models = modelsRef.current
    if (!video || !models || video.readyState < 2 || video.videoWidth === 0) return
    if (busyRef.current) return

    busyRef.current = true
    try {
      // MediaPipe requires strictly increasing timestamps.
      const timestamp = Math.max(Math.round(performance.now()), lastTimestampRef.current + 1)
      lastTimestampRef.current = timestamp

      const faceResult = models.face.detectForVideo(video, timestamp)
      const face = faceMetrics(faceResult, headHistoryRef.current)

      let pose = lastPoseRef.current.metrics
      if (timestamp - lastPoseRef.current.at >= POSE_MIN_INTERVAL_MS) {
        const poseResult = models.pose.detectForVideo(video, timestamp)
        pose = postureFromPose(poseResult?.landmarks?.[0])
        lastPoseRef.current = { at: timestamp, metrics: pose }
      }

      const metrics = {
        frame_ok: true,
        ...face,
        ...pose,
        errors: [],
      }

      const rawConfidence = fuseConfidence(metrics)
      if (rawConfidence != null && metrics.face_present) {
        const previous = smoothedConfidenceRef.current
        metrics.confidence = previous == null
          ? rawConfidence
          : round1(previous + (rawConfidence - previous) * CONFIDENCE_SMOOTHING)
        smoothedConfidenceRef.current = metrics.confidence
      } else {
        metrics.confidence = rawConfidence ?? 0
      }

      const frame = {
        ...metrics,
        ts_ms: Date.now() - startTsRef.current,
      }
      historyRef.current.push(frame)
      // Keep memory bounded for very long sessions (~10 minutes at 5 fps).
      if (historyRef.current.length > 3000) historyRef.current.shift()
      setFrames(historyRef.current.length)
      setLatest(metrics)
    } catch (err) {
      setCoachStatus('error')
      setError(
        `Live analysis stopped: ${err?.message || 'the vision model could not process the camera feed'}.`,
      )
      window.clearInterval(timerRef.current)
      timerRef.current = null
    } finally {
      busyRef.current = false
    }
  }, [])

  const start = useCallback(async (video) => {
    if (!video) return
    if (!window.WebGLRenderingContext && !window.WebAssembly) {
      setCoachStatus('error')
      setError('This browser cannot run the local vision models. Try a recent Chrome, Edge or Firefox.')
      return
    }

    videoRef.current = video
    startTsRef.current = Date.now()
    lastTimestampRef.current = 0
    lastPoseRef.current = { at: 0, metrics: postureFromPose(null) }
    headHistoryRef.current = []
    setCoachStatus('connecting')
    setError(null)

    try {
      modelsRef.current = await loadModels()
      if (videoRef.current !== video) return // stopped while loading
      setCoachStatus('live')
      window.clearInterval(timerRef.current)
      timerRef.current = window.setInterval(processFrame, 1000 / FPS)
      processFrame()
    } catch (err) {
      modelsRef.current = null
      setCoachStatus('error')
      setError(
        `Could not load the on-device vision models${err?.message ? `: ${err.message}` : ''}. ` +
        'Check that /mediapipe/ assets are available and reload the page.',
      )
    }
  }, [processFrame])

  const stop = useCallback(() => {
    window.clearInterval(timerRef.current)
    timerRef.current = null
    videoRef.current = null
    if (statusRef.current !== 'error') setCoachStatus('idle')
  }, [])

  const reset = useCallback(() => {
    historyRef.current = []
    smoothedConfidenceRef.current = null
    setFrames(0)
    setLatest(null)
    lastPoseRef.current = { at: 0, metrics: postureFromPose(null) }
    headHistoryRef.current = []
  }, [])

  useEffect(() => () => {
    window.clearInterval(timerRef.current)
    timerRef.current = null
  }, [])

  const aggregate = useCallback(() => aggregateFrames(historyRef.current), [])

  return { status, latest, error, start, stop, reset, aggregate, frameCount: frames }
}
