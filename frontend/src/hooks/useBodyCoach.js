import { useCallback, useEffect, useRef, useState } from 'react'

const FPS = 5
const MAX_FRAME_WIDTH = 320
const JPEG_QUALITY = 0.7

function wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/coach`
}

function jpegBytesFromDataUrl(dataUrl) {
  const base64 = dataUrl.split(',')[1] ?? ''
  const bin = atob(base64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
  return bytes.buffer
}

function avg(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
}

function aggregateFrames(frames) {
  if (!frames.length) return {}
  const n = frames.length
  const pct = (key) => (100 * frames.filter((f) => f[key]).length) / n
  const ts = frames.map((f) => f.ts_ms).filter(Boolean)
  const duration =
    ts.length >= 2 && Math.max(...ts) > Math.min(...ts)
      ? (Math.max(...ts) - Math.min(...ts)) / 1000
      : n / FPS

  const statuses = frames.map((f) => f.posture ?? 'unknown')
  const shifts = statuses.reduce((acc, s, i) => {
    const prev = statuses[i - 1]
    return prev && s !== prev && s !== 'unknown' && prev !== 'unknown' ? acc + 1 : acc
  }, 0)
  const breakdown = {}
  statuses.forEach((s) => {
    breakdown[s] = (breakdown[s] ?? 0) + 1
  })

  const confidence = frames
    .filter((f) => f.face_present && typeof f.confidence === 'number')
    .map((f) => f.confidence)

  return {
    eye_contact_pct: Math.round(avg(frames.map((f) => f.eye_contact_pct ?? 0)) * 10) / 10,
    face_present_pct: Math.round(pct('face_present') * 10) / 10,
    smile_pct: Math.round(pct('smiling') * 10) / 10,
    head_steady_pct: Math.round(pct('head_steady') * 10) / 10,
    blink_rate_per_min:
      duration > 0
        ? Math.round(((frames.filter((f) => f.blink).length * 60) / duration) * 10) / 10
        : null,
    posture_shift_count: shifts,
    duration_seconds: Math.round(duration * 10) / 10,
    posture_breakdown: breakdown,
    confidence_pct: confidence.length ? Math.round(avg(confidence) * 10) / 10 : null,
  }
}

export default function useBodyCoach() {
  const [status, setStatus] = useState('idle') // idle | connecting | live | error
  const [latest, setLatest] = useState(null)
  const [error, setError] = useState(null)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const wsRef = useRef(null)
  const timerRef = useRef(null)
  const historyRef = useRef([])
  const startTsRef = useRef(0)

  const sendFrame = useCallback(() => {
    const ws = wsRef.current
    const video = videoRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN || !video || video.readyState < 2) return
    if (ws.bufferedAmount > 128 * 1024) return // backpressure: drop frames

    const canvas = canvasRef.current ?? document.createElement('canvas')
    canvasRef.current = canvas
    const scale = Math.min(1, MAX_FRAME_WIDTH / video.videoWidth)
    canvas.width = Math.round(video.videoWidth * scale)
    canvas.height = Math.round(video.videoHeight * scale)
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
    ws.send(jpegBytesFromDataUrl(dataUrl))
  }, [])

  const start = useCallback(
    (video) => {
      if (!video || !window.WebSocket) {
        setStatus('error')
        setError('WebSocket not supported in this browser.')
        return
      }
      videoRef.current = video
      startTsRef.current = Date.now()
      setStatus('connecting')
      setError(null)

      const ws = new WebSocket(wsUrl())
      wsRef.current = ws
      ws.binaryType = 'arraybuffer'

      ws.onopen = () => {
        setStatus('live')
        timerRef.current = window.setInterval(sendFrame, 1000 / FPS)
      }
      ws.onmessage = (event) => {
        try {
          const metrics = JSON.parse(event.data)
          const frame = { ...metrics, ts_ms: Date.now() - startTsRef.current }
          historyRef.current.push(frame)
          setLatest(metrics)
        } catch {
          // ignore malformed frames
        }
      }
      ws.onerror = () => {
        setStatus('error')
        setError('Could not reach the AI coach stream.')
      }
      ws.onclose = () => {
        window.clearInterval(timerRef.current)
        timerRef.current = null
        if (status !== 'error') setStatus('idle')
      }
    },
    [sendFrame, status],
  )

  const stop = useCallback(() => {
    window.clearInterval(timerRef.current)
    timerRef.current = null
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    videoRef.current = null
    setStatus('idle')
  }, [])

  const reset = useCallback(() => {
    historyRef.current = []
  }, [])

  useEffect(() => () => stop(), [stop])

  const aggregate = useCallback(() => aggregateFrames(historyRef.current), [])
  const frameCount = historyRef.current.length

  return { status, latest, error, start, stop, reset, aggregate, frameCount }
}
