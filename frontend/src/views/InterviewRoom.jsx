import { useEffect, useRef, useState } from 'react'
import useMediaDevices from '../hooks/useMediaDevices.js'
import useSpeechRecognition from '../hooks/useSpeechRecognition.js'
import useBodyCoach from '../hooks/useBodyCoach.js'
import CodingEditor from '../components/CodingEditor.jsx'
import { Spinner, Badge } from '../components/ui.jsx'
import { api } from '../api/client.js'
import {
  MicIcon,
  MicOffIcon,
  VideoIcon,
  VideoOffIcon,
  StopIcon,
  ClockIcon,
  CheckIcon,
  ArrowRightIcon,
  BriefcaseIcon,
  BrainIcon,
  UsersIcon,
} from '../components/icons.jsx'

const ROUND_ICONS = { managerial: BriefcaseIcon, technical: BrainIcon, hr: UsersIcon }

const QUESTION_SECONDS = 120

const POSTURE_LABELS = {
  good: { text: 'Good posture', cls: 'bg-emerald-100 text-emerald-700' },
  slouching: { text: 'Slouching', cls: 'bg-amber-100 text-amber-700' },
  leaning_left: { text: 'Leaning left', cls: 'bg-amber-100 text-amber-700' },
  leaning_right: { text: 'Leaning right', cls: 'bg-amber-100 text-amber-700' },
  too_close: { text: 'Too close', cls: 'bg-amber-100 text-amber-700' },
  too_far: { text: 'Too far', cls: 'bg-amber-100 text-amber-700' },
  unknown: { text: 'Posture —', cls: 'bg-slate-100 text-slate-500' },
}

export default function InterviewRoom({ session, onExit, onFinish }) {
  const { stream, videoActive, micActive, error, requesting, start, toggleVideo, toggleMic } =
    useMediaDevices()
  const {
    supported: speechSupported,
    listening,
    finalTranscript,
    interimTranscript,
    start: startSpeech,
    stop: stopSpeech,
    reset: resetSpeech,
  } = useSpeechRecognition()

  const videoRef = useRef(null)
  const meterRef = useRef(null)
  const speechStartedAt = useRef(null)
  const recorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const recordedAudioRef = useRef(null)
  const coach = useBodyCoach()

  const [roundIndex, setRoundIndex] = useState(0)
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [answerText, setAnswerText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [errorMessage, setErrorMessage] = useState(null)
  const [hasRecording, setHasRecording] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(QUESTION_SECONDS)

  const audioSupported = typeof MediaRecorder !== 'undefined'

  const rounds = session.rounds
  const round = rounds[roundIndex]
  const question = round.questions[questionIndex]
  const isLastQuestion = roundIndex === rounds.length - 1 && questionIndex === round.questions.length - 1

  useEffect(() => {
    setSecondsLeft(QUESTION_SECONDS)
    if (question.type === 'coding') return undefined
    const interval = setInterval(() => {
      setSecondsLeft((s) => (s > 0 ? s - 1 : 0))
    }, 1000)
    return () => clearInterval(interval)
  }, [roundIndex, questionIndex, question.type])

  const timerLabel = `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, '0')}`
  const timerColor =
    secondsLeft > 60 ? 'text-emerald-600' : secondsLeft > 30 ? 'text-amber-600' : 'text-rose-600'

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream
    }
  }, [stream])

  useEffect(() => {
    if (stream && videoActive && videoRef.current) {
      coach.start(videoRef.current)
    } else {
      coach.stop()
    }
    return () => coach.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream, videoActive])

  useEffect(() => {
    if (!stream || !micActive) return undefined
    const AudioContext = window.AudioContext || window.webkitAudioContext
    if (!AudioContext) return undefined
    const ctx = new AudioContext()
    const source = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
    const data = new Uint8Array(analyser.fftSize)
    let frameId
    const tick = () => {
      analyser.getByteTimeDomainData(data)
      let sum = 0
      for (let i = 0; i < data.length; i += 1) {
        const v = (data[i] - 128) / 128
        sum += v * v
      }
      const level = Math.min(1, Math.sqrt(sum / data.length) * 4)
      if (meterRef.current) meterRef.current.style.width = `${Math.round(level * 100)}%`
      frameId = requestAnimationFrame(tick)
    }
    frameId = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frameId)
      source.disconnect()
      ctx.close()
    }
  }, [stream, micActive])

  const toggleRecording = () => {
    if (listening) {
      stopSpeech()
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop()
      }
    } else {
      recordedAudioRef.current = null
      setHasRecording(false)
      speechStartedAt.current = Date.now()
      startSpeech()
      if (audioSupported && stream && micActive) {
        audioChunksRef.current = []
        try {
          const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
          recorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunksRef.current.push(e.data)
          }
          recorder.onstop = () => {
            recordedAudioRef.current = new Blob(audioChunksRef.current, { type: recorder.mimeType })
            setHasRecording(recordedAudioRef.current.size > 0)
          }
          recorderRef.current = recorder
          recorder.start()
        } catch {
          recorderRef.current = null
        }
      }
    }
  }

  function stopRecorder() {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
    recorderRef.current = null
  }

  const transcribed = `${finalTranscript}${interimTranscript ? ' ' + interimTranscript : ''}`.trim()
  const currentAnswer = answerText || transcribed

  function goToQuestion(nextRound, nextQuestion) {
    setRoundIndex(nextRound)
    setQuestionIndex(nextQuestion)
    setAnswerText('')
    setFeedback(null)
    setErrorMessage(null)
    resetSpeech()
    stopSpeech()
    stopRecorder()
    recordedAudioRef.current = null
    setHasRecording(false)
    coach.reset()
  }

  async function handleSubmitAnswer() {
    if (!currentAnswer.trim()) return
    setSubmitting(true)
    setErrorMessage(null)
    try {
      const duration = listening || speechStartedAt.current
        ? (Date.now() - (speechStartedAt.current || Date.now())) / 1000
        : 1
      const body_metrics = coach.aggregate()
      const data = await api.submitAnswer(session.id, {
        round_id: round.id,
        question: question.question,
        category: question.category,
        difficulty: question.difficulty,
        type: 'theory',
        answer: answerText.trim(),
        transcript: transcribed,
        duration_seconds: Math.max(duration, 1),
        body_metrics,
      })
      setAnswers((prev) => ({ ...prev, [question.id]: data }))
      setFeedback(data)
      if (recordedAudioRef.current) {
        try {
          await api.uploadAnswerAudio(session.id, data.answer_id, recordedAudioRef.current)
        } catch {
          // audio upload is best-effort; the answer is already saved
        }
        recordedAudioRef.current = null
        setHasRecording(false)
      }
      coach.reset()
    } catch (err) {
      setErrorMessage(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSubmitCoding(code, runResult) {
    setSubmitting(true)
    setErrorMessage(null)
    try {
      const data = await api.submitCoding(session.id, {
        challenge_id: question.challenge_id,
        code,
        language: question.language,
        title: question.title,
        difficulty: question.difficulty,
        round_id: round.id,
      })
      setAnswers((prev) => ({ ...prev, [question.id]: data }))
      setFeedback({ score: data.score, passed: data.passed, total: data.total, coding: true, feedback: data.feedback })
    } catch (err) {
      setErrorMessage(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  function getNextPosition() {
    if (questionIndex < round.questions.length - 1) return [roundIndex, questionIndex + 1]
    if (roundIndex < rounds.length - 1) return [roundIndex + 1, 0]
    return null
  }

  function handleNext() {
    const next = getNextPosition()
    if (!next) {
      finishInterview()
      return
    }
    goToQuestion(...next)
  }

  async function finishInterview() {
    const unanswered = rounds.reduce(
      (n, r) => n + r.questions.filter((q) => !answers[q.id]).length,
      0,
    )
    if (
      unanswered > 0 &&
      !window.confirm(
        `You still have ${unanswered} unanswered question${unanswered === 1 ? '' : 's'}. Finish the interview now?`,
      )
    ) {
      return
    }
    setSubmitting(true)
    try {
      const data = await api.completeSession(session.id)
      onFinish(data)
    } catch (err) {
      setErrorMessage(err.message)
      setSubmitting(false)
    }
  }

  const roundAnswered = (idx) => {
    const r = rounds[idx]
    return r.questions.filter((q) => answers[q.id]).length
  }

  const stepClass = (idx) => {
    if (idx === roundIndex) return 'border-brand-600 bg-brand-600 text-white'
    if (roundAnswered(idx) === rounds[idx].questions.length && rounds[idx].questions.length > 0)
      return 'border-emerald-300 bg-emerald-50 text-emerald-700'
    return 'border-slate-200 bg-white text-slate-500'
  }

  const scoreTileCls =
    (feedback?.score ?? 0) >= 8
      ? 'bg-emerald-50 text-emerald-700'
      : (feedback?.score ?? 0) >= 6
        ? 'bg-amber-50 text-amber-700'
        : 'bg-rose-50 text-rose-700'

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <button
            type="button"
            onClick={onExit}
            className="btn btn-ghost -ml-2 text-sm"
          >
            Exit
          </button>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 shadow-sm">
              <MicIcon className="h-5 w-5 text-white" />
            </span>
            <span className="hidden font-extrabold tracking-tight text-slate-900 sm:inline">
              Speak<span className="text-brand-600">2Success</span>
            </span>
            <span className="ml-2 hidden rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 md:inline">
              {session.role}
              {session.name ? ` · ${session.name}` : ''}
            </span>
          </div>
          <button
            type="button"
            onClick={finishInterview}
            disabled={submitting}
            className="btn btn-secondary text-xs"
          >
            Finish interview
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6">
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <section>
            {/* Round stepper */}
            <div className="mb-4 grid grid-cols-3 gap-2">
              {rounds.map((r, idx) => {
                const done = roundAnswered(idx)
                const total = r.questions.length
                const RoundIcon = ROUND_ICONS[r.id] ?? BrainIcon
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => goToQuestion(idx, 0)}
                    className={`flex items-center gap-2.5 rounded-xl border px-3 py-2 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ${stepClass(idx)}`}
                  >
                    <RoundIcon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-bold">{r.name}</span>
                      <span className={`block text-[10px] ${idx === roundIndex ? 'text-white/80' : 'opacity-70'}`}>
                        {done}/{total} answered
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Question card */}
            <div className="card">
              <div className="flex items-center gap-3 border-b border-slate-200 px-6 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-extrabold text-white">
                  AI
                </div>
                <div>
                  <p className="font-bold text-slate-900">AI Interviewer · {round.name}</p>
                  <p className="text-xs text-slate-500">
                    Question {questionIndex + 1} of {round.questions.length}
                    {question.difficulty ? ` · ${question.difficulty}` : ''}
                  </p>
                </div>
                {question.type === 'theory' && !feedback && (
                  <span
                    className={`ml-auto flex items-center gap-1.5 text-sm font-bold tabular-nums ${timerColor}`}
                    title="Time remaining"
                  >
                    <ClockIcon className="h-4 w-4" />
                    {timerLabel}
                  </span>
                )}
                {question.type === 'coding' && (
                  <Badge tone="emerald" className="ml-auto">
                    <BrainIcon className="h-3.5 w-3.5" />
                    Coding · {question.language}
                  </Badge>
                )}
              </div>

              <div className="p-6">
                {!feedback && (
                  <>
                    <p className="text-lg font-medium leading-relaxed text-slate-800">
                      {question.type === 'coding' ? question.title : question.question}
                    </p>

                    {question.type === 'coding' ? (
                      <div className="mt-4">
                        <CodingEditor
                          challenge={question}
                          language={question.language}
                          onSubmit={handleSubmitCoding}
                        />
                      </div>
                    ) : (
                      <div className="mt-5 space-y-4">
                        {speechSupported ? (
                          <div>
                            <button
                              type="button"
                              onClick={toggleRecording}
                    className={`btn text-sm ${
                      listening
                        ? 'bg-rose-600 text-white hover:bg-rose-700'
                        : 'btn-secondary'
                    }`}
                            >
                              {listening ? (
                                <>
                                  <StopIcon className="mr-1.5 inline h-4 w-4" />
                                  Stop recording
                                </>
                              ) : (
                                <>
                                  <MicIcon className="mr-1.5 inline h-4 w-4" />
                                  Record answer
                                </>
                              )}
                            </button>
                            <div className="mt-2 flex min-h-[44px] flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
                              {transcribed ? (
                                <span className="flex-1">
                                  {finalTranscript}
                                  <span className="text-slate-400">{interimTranscript ? ' ' + interimTranscript : ''}</span>
                                </span>
                              ) : listening ? (
                                <span className="flex-1 animate-pulse text-rose-500">Listening… speak now</span>
                              ) : (
                                <span className="flex-1">Speak your answer, or type it below.</span>
                              )}
                              {listening && audioSupported && stream && micActive && (
                                <span className="flex items-center gap-1.5 rounded-full bg-rose-600 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white">
                                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
                                  Audio
                                </span>
                              )}
                              {hasRecording && (
                                <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
                                  <CheckIcon className="h-3 w-3" />
                                  Recorded with your answer
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-400">
                            Speech recognition isn't supported in this browser — type your answer below.
                          </p>
                        )}

                        <textarea
                          value={answerText}
                          onChange={(e) => setAnswerText(e.target.value)}
                          rows={4}
                          placeholder="Your answer (typed or transcribed)…"
                          className="input"
                        />

                        {errorMessage && (
                          <p className="rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">{errorMessage}</p>
                        )}

                        <button
                          type="button"
                          onClick={handleSubmitAnswer}
                          disabled={submitting || !currentAnswer.trim()}
                          className="btn-primary w-full"
                        >
                          {submitting && <Spinner className="h-4 w-4" />}
                          {submitting ? 'Evaluating your answer…' : 'Submit answer'}
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            const next = getNextPosition()
                            if (next) goToQuestion(...next)
                            else finishInterview()
                          }}
                          disabled={submitting}
                          className="btn btn-ghost w-full text-sm"
                        >
                          Skip this question
                          <ArrowRightIcon className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </>
                )}

                {feedback && (
                  <div className="space-y-5">
                    <div className="flex items-center gap-4">
                      <div
                        className={`flex h-16 w-16 items-center justify-center rounded-2xl text-2xl font-extrabold ${scoreTileCls}`}
                      >
                        {feedback.score}
                      </div>
                      <div>
                        <p className="font-bold text-slate-900">Answer evaluated</p>
                        <p className="text-xs text-slate-500">
                          {feedback.coding
                            ? `Hidden tests: ${feedback.passed}/${feedback.total} passed`
                            : `Word count ${feedback.feedback?.word_count ?? '—'} · Fillers ${feedback.feedback?.filler_word_count ?? '—'}`}
                        </p>
                      </div>
                    </div>

                    {!feedback.coding && (
                      <div className="grid gap-3 sm:grid-cols-2">
                        {feedback.feedback?.suggestions && (
                          <ul className="space-y-2 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
                            {feedback.feedback.suggestions.map((s) => (
                              <li key={s} className="flex gap-2.5">
                                <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                                <span>{s}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                        {feedback.speech && (
                          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
                            <p className="font-semibold text-slate-800">Speech</p>
                            <p className="mt-1">
                              {feedback.speech.words_per_minute} WPM · clarity{' '}
                              {feedback.speech.clarity_score}/10 · {feedback.speech.total_filler_words}{' '}
                              filler words
                            </p>
                            {feedback.speech.suggestions.map((s) => (
                              <p key={s} className="mt-1 text-xs text-slate-500">
                                {s}
                              </p>
                            ))}
                          </div>
                        )}
                        {feedback.body_language && (
                          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
                            <p className="font-semibold text-slate-800">
                              Body language · {feedback.body_language.score}/10
                            </p>
                            {feedback.body_language.suggestions.map((s) => (
                              <p key={s} className="mt-1 text-xs text-slate-500">
                                {s}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {errorMessage && (
                      <p className="rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">{errorMessage}</p>
                    )}

                    <button
                      type="button"
                      onClick={handleNext}
                      disabled={submitting}
                      className="btn btn-success w-full"
                    >
                      {isLastQuestion ? 'View Success Report' : 'Next question'}
                      <ArrowRightIcon className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Webcam panel */}
          <aside className="space-y-3">
            <div className="relative aspect-[3/4] overflow-hidden rounded-2xl bg-slate-900 shadow-lg">
              {!stream && !requesting && !error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-4 text-center">
                  <button
                    type="button"
                    onClick={start}
                    className="btn btn-primary"
                  >
                    <VideoIcon className="h-4 w-4" />
                    Enable camera &amp; mic
                  </button>
                  <p className="text-xs text-slate-400">
                    A professional interview needs both. You can toggle them anytime.
                  </p>
                </div>
              )}
              {requesting && (
                <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-slate-400">
                  <Spinner className="h-4 w-4" />
                  Requesting access…
                </div>
              )}
              {error && (
                <div className="absolute inset-0 flex items-center justify-center p-4 text-center text-xs text-rose-300">
                  {error}
                </div>
              )}
              {stream && (
                <>
                  <video
                    ref={videoRef}
                    autoPlay
                    muted
                    playsInline
                    className={`h-full w-full object-cover transition ${videoActive ? '' : 'opacity-0'}`}
                    style={{ transform: 'scaleX(-1)' }}
                  />
                  {!videoActive && (
                    <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm font-medium text-slate-400">
                      <VideoOffIcon className="h-4 w-4" />
                      Camera off
                    </div>
                  )}
                  <div className="absolute left-3 top-3 flex items-center gap-2">
                    {micActive && listening ? (
                      <span className="flex items-center gap-1.5 rounded-full bg-rose-600 px-2.5 py-1 text-xs font-semibold text-white">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
                        REC
                      </span>
                    ) : (
                      micActive && (
                        <span className="rounded-full bg-slate-700/80 px-2.5 py-1 text-xs font-semibold text-white">
                          You
                        </span>
                      )
                    )}
                  </div>
                  <div className="absolute bottom-3 left-3 right-3">
                    <div className="flex items-end gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700">
                        <div ref={meterRef} className="h-full rounded-full bg-emerald-400" style={{ width: '0%' }} />
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            {stream && (
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={toggleVideo}
                  className={`btn text-xs ${videoActive ? 'btn-secondary' : 'btn-danger'}`}
                >
                  {videoActive ? <VideoIcon className="h-4 w-4" /> : <VideoOffIcon className="h-4 w-4" />}
                  {videoActive ? 'Video on' : 'Video off'}
                </button>
                <button
                  type="button"
                  onClick={toggleMic}
                  className={`btn text-xs ${micActive ? 'btn-secondary' : 'btn-danger'}`}
                >
                  {micActive ? <MicIcon className="h-4 w-4" /> : <MicOffIcon className="h-4 w-4" />}
                  {micActive ? 'Mic on' : 'Mic off'}
                </button>
              </div>
            )}

            {/* AI Coach panel */}
            <div className="card p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold text-slate-900">AI Coach</p>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                    coach.status === 'live'
                      ? 'bg-emerald-100 text-emerald-700'
                      : coach.status === 'connecting'
                        ? 'animate-pulse bg-amber-100 text-amber-700'
                        : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {coach.status}
                </span>
              </div>
              <p className="mt-0.5 text-[10px] text-slate-400">
                Live posture &amp; engagement tracking · {coach.frameCount} frames
              </p>

              {coach.error ? (
                <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{coach.error}</p>
              ) : coach.status === 'live' && coach.latest ? (
                <div className="mt-3 space-y-3">
                  <div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-600">Confidence</span>
                      <span className="font-bold text-slate-800">{Math.round(coach.latest.confidence ?? 0)}%</span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full transition-all ${
                          coach.latest.confidence >= 70
                            ? 'bg-emerald-400'
                            : coach.latest.confidence >= 50
                              ? 'bg-amber-400'
                              : 'bg-rose-400'
                        }`}
                        style={{ width: `${Math.round(coach.latest.confidence ?? 0)}%` }}
                      />
                    </div>
                    <div className="mt-0.5 text-[10px] font-medium text-slate-400">
                      {!coach.latest.face_present
                        ? 'No face detected'
                        : coach.latest.confidence >= 70
                          ? 'Confident — calm, steady delivery'
                          : coach.latest.confidence >= 50
                            ? 'Composed — relax into the camera'
                            : 'Nervous — breathe and steady yourself'}
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-800">{Math.round(coach.latest.eye_contact_pct)}%</span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full transition-all ${
                          coach.latest.eye_contact_pct >= 60 ? 'bg-emerald-400' : 'bg-amber-400'
                        }`}
                        style={{ width: `${coach.latest.eye_contact_pct}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(() => {
                      const p = POSTURE_LABELS[coach.latest.posture] ?? POSTURE_LABELS.unknown
                      return (
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${p.cls}`}>
                          <CheckIcon className="mr-1 inline h-3 w-3" />
                          {p.text}
                        </span>
                      )
                    })()}
                    {coach.latest.smiling ? (
                      <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                        <CheckIcon className="h-3 w-3" />
                        Smiling
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                        Neutral
                      </span>
                    )}
                    {!coach.latest.face_present && (
                      <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-700">
                        <CheckIcon className="h-3 w-3" />
                        No face detected
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                    <span className="font-medium text-slate-600">Tip:</span>
                    <span>
                      {coach.latest.eye_contact_pct < 60
                        ? 'Look into the camera lens while speaking.'
                        : coach.latest.posture === 'slouching'
                          ? 'Sit upright with both feet on the floor.'
                          : coach.latest.posture !== 'good' && coach.latest.posture !== 'unknown'
                            ? 'Adjust your seating so you face the camera squarely.'
                            : 'Great — you look engaged. Keep it up.'}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-xs text-slate-400">
                  {coach.status === 'connecting'
                    ? 'Connecting to the coach…'
                    : 'Enable the camera to start real-time posture tracking.'}
                </p>
              )}
            </div>

              <p className="px-2 text-center text-xs leading-relaxed text-slate-400">
              Your video stays in your browser. Only posture metrics and transcribed speech are
              sent for analysis.
            </p>
          </aside>
        </div>
      </main>
    </div>
  )
}
