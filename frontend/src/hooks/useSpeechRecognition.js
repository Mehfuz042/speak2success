import { useCallback, useEffect, useRef, useState } from 'react'

const SR = window.SpeechRecognition || window.webkitSpeechRecognition

export default function useSpeechRecognition() {
  const [supported] = useState(() => Boolean(SR))
  const [listening, setListening] = useState(false)
  const [finalTranscript, setFinalTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const recognitionRef = useRef(null)

  const getRecognition = () => {
    if (!SR) return null
    if (!recognitionRef.current) {
      const recognition = new SR()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-US'
      recognitionRef.current = recognition
    }
    return recognitionRef.current
  }

  const start = useCallback(() => {
    const recognition = getRecognition()
    if (!recognition) return
    setFinalTranscript('')
    setInterimTranscript('')
    setListening(true)
    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = event.results[i][0].transcript
        if (event.results[i].isFinal) final += chunk
        else interim += chunk
      }
      setFinalTranscript((prev) => prev + final)
      setInterimTranscript(interim)
    }
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    try {
      recognition.start()
    } catch {
      // already started - ignore
    }
  }, [])

  const stop = useCallback(() => {
    const recognition = getRecognition()
    setListening(false)
    if (recognition) {
      recognition.onend = null
      try {
        recognition.stop()
      } catch {
        // not running - ignore
      }
    }
  }, [])

  const reset = useCallback(() => {
    setFinalTranscript('')
    setInterimTranscript('')
  }, [])

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.onresult = null
        recognitionRef.current.onend = null
        try {
          recognitionRef.current.stop()
        } catch {
          // ignore
        }
      }
    }
  }, [])

  return { supported, listening, finalTranscript, interimTranscript, start, stop, reset }
}
