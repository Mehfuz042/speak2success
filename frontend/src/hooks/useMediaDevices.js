import { useCallback, useEffect, useRef, useState } from 'react'

const ERROR_MESSAGES = {
  NotAllowedError:
    'Camera and/or microphone access was denied. Allow access in your browser settings and try again.',
  NotFoundError: 'No camera or microphone was found on this device.',
  NotReadableError: 'Your camera or microphone is already in use by another application.',
  OverconstrainedError: 'The requested camera or microphone settings are not supported.',
}

export default function useMediaDevices() {
  const [stream, setStream] = useState(null)
  const [videoActive, setVideoActive] = useState(false)
  const [micActive, setMicActive] = useState(false)
  const [error, setError] = useState(null)
  const [requesting, setRequesting] = useState(false)
  const streamRef = useRef(null)

  const syncActive = (mediaStream) => {
    setVideoActive(mediaStream?.getVideoTracks().some((track) => track.enabled) ?? false)
    setMicActive(mediaStream?.getAudioTracks().some((track) => track.enabled) ?? false)
  }

  const start = useCallback(async () => {
    if (streamRef.current) {
      syncActive(streamRef.current)
      return streamRef.current
    }
    setRequesting(true)
    setError(null)
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: true,
      })
      streamRef.current = mediaStream
      setStream(mediaStream)
      syncActive(mediaStream)
      return mediaStream
    } catch (err) {
      setError(
        ERROR_MESSAGES[err.name] ||
          `Could not access your camera or microphone (${err.name}).`,
      )
      throw err
    } finally {
      setRequesting(false)
    }
  }, [])

  const toggleVideo = useCallback(() => {
    const mediaStream = streamRef.current
    if (!mediaStream) return
    const next = !mediaStream.getVideoTracks().some((track) => track.enabled)
    mediaStream.getVideoTracks().forEach((track) => {
      track.enabled = next
    })
    setVideoActive(next)
  }, [])

  const toggleMic = useCallback(() => {
    const mediaStream = streamRef.current
    if (!mediaStream) return
    const next = !mediaStream.getAudioTracks().some((track) => track.enabled)
    mediaStream.getAudioTracks().forEach((track) => {
      track.enabled = next
    })
    setMicActive(next)
  }, [])

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setStream(null)
    setVideoActive(false)
    setMicActive(false)
    setError(null)
  }, [])

  useEffect(() => {
    return () => stop()
  }, [stop])

  return { stream, videoActive, micActive, error, requesting, start, toggleVideo, toggleMic, stop }
}
