import { useEffect, useState } from 'react'
import Home from './views/Home.jsx'
import Setup from './views/Setup.jsx'
import InterviewRoom from './views/InterviewRoom.jsx'
import Review from './views/Review.jsx'
import History from './views/History.jsx'
import BrandHeader from './components/BrandHeader.jsx'
import { Spinner } from './components/ui.jsx'
import { api } from './api/client.js'
import { AlertIcon } from './components/icons.jsx'

const STORAGE_KEYS = {
  session: 's2s_active_session',
  review: 's2s_last_review',
  sessionId: 's2s_last_session_id',
}

function read(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function write(key, value) {
  localStorage.setItem(key, JSON.stringify(value))
}

function clear(key) {
  localStorage.removeItem(key)
}

function ReportLoader({ sessionId, onExit, onRestart }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setData(null)
    setError(null)
    api
      .getSession(sessionId)
      .then((payload) => {
        if (!alive) return
        if (payload.session.status !== 'completed' || !payload.review) {
          setError("This interview hasn't been completed yet.")
          return
        }
        setData(payload)
      })
      .catch((err) => alive && setError(err.message))
    return () => {
      alive = false
    }
  }, [sessionId])

  if (error) {
    return (
      <div className="flex min-h-screen flex-col bg-slate-50">
        <BrandHeader
          right={
            <button type="button" onClick={onExit} className="btn btn-secondary text-xs">
              Back to history
            </button>
          }
        />
        <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 text-rose-600">
            <AlertIcon className="h-7 w-7" />
          </div>
          <p className="font-semibold text-slate-700">{error}</p>
          <button type="button" onClick={onExit} className="btn btn-primary">
            Back to history
          </button>
        </main>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex min-h-screen flex-col bg-slate-50">
        <BrandHeader />
        <main className="flex flex-1 items-center justify-center gap-2 text-sm text-slate-400">
          <Spinner className="h-4 w-4" />
          Loading your Success Report…
        </main>
      </div>
    )
  }

  return <Review review={data.review} session={data.session} onExit={onExit} onRestart={onRestart} />
}

export default function App() {
  const [route, setRoute] = useState(window.location.hash || '#/')
  const [session, setSession] = useState(() => read(STORAGE_KEYS.session))
  const [reviewData, setReviewData] = useState(() => read(STORAGE_KEYS.review))

  useEffect(() => {
    const onHash = () => setRoute(window.location.hash || '#/')
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const path = route.replace(/^#/, '')

  // Live-reload the session (answers progress) whenever the room mounts.
  useEffect(() => {
    if (!session) return undefined
    let alive = true
    api
      .getSession(session.id)
      .then((data) => {
        if (alive && data.session.status !== 'completed') {
          setSession(data.session)
          write(STORAGE_KEYS.session, data.session)
        }
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [session?.id])

  function startInterview(nextSession) {
    write(STORAGE_KEYS.session, nextSession)
    setSession(nextSession)
    window.location.hash = '#/interview'
  }

  function finishInterview(payload) {
    write(STORAGE_KEYS.review, payload)
    setReviewData(payload)
    clear(STORAGE_KEYS.session)
    setSession(null)
    window.location.hash = '#/review'
  }

  function restart() {
    clear(STORAGE_KEYS.session)
    clear(STORAGE_KEYS.review)
    setSession(null)
    setReviewData(null)
    window.location.hash = '#/setup'
  }

  function exit() {
    clear(STORAGE_KEYS.session)
    setSession(null)
    window.location.hash = '#/'
  }

  function goToSetup() {
    window.location.hash = '#/setup'
  }

  function goToHistory() {
    window.location.hash = '#/history'
  }

  if (path.startsWith('/report/')) {
    const sessionId = decodeURIComponent(path.split('/')[2])
    return (
      <ReportLoader sessionId={sessionId} onExit={goToHistory} onRestart={restart} />
    )
  }

  if (path.startsWith('/history')) {
    return (
      <History
        onBack={exit}
        onOpen={(id) => (id ? (window.location.hash = `#/report/${encodeURIComponent(id)}`) : goToSetup())}
      />
    )
  }

  if (path.startsWith('/review')) {
    return (
      <Review
        review={reviewData?.review}
        session={reviewData?.session}
        onExit={exit}
        onRestart={restart}
      />
    )
  }

  if (path.startsWith('/interview')) {
    if (!session) {
      window.location.hash = '#/setup'
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50">
          <Spinner className="h-5 w-5 text-slate-400" />
        </div>
      )
    }
    return <InterviewRoom session={session} onExit={exit} onFinish={finishInterview} />
  }

  if (path.startsWith('/setup')) {
    return <Setup onStart={startInterview} onBack={exit} />
  }

  return <Home onStart={goToSetup} onHistory={goToHistory} />
}
