import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import BrandHeader from '../components/BrandHeader.jsx'
import { Badge, Card } from '../components/ui.jsx'
import {
  MicIcon,
  VideoIcon,
  ChartIcon,
  BrainIcon,
  ArrowRightIcon,
  SparklesIcon,
  CheckIcon,
} from '../components/icons.jsx'

const FEATURES = [
  {
    icon: MicIcon,
    title: 'AI Mock Interviews',
    text: 'A Gemini-powered interviewer asks questions and adapts to your answers in real time, just like the real thing.',
  },
  {
    icon: VideoIcon,
    title: 'Body-Language Coaching',
    text: 'Your posture, eye contact and gestures are tracked live while you speak, with on-the-spot hints.',
  },
  {
    icon: ChartIcon,
    title: 'Success Report',
    text: 'Afterwards, get a full scorecard on your answering technique and delivery with actionable tips.',
  },
]

export default function Home({ onStart, onHistory }) {
  const [name, setName] = useState(() => localStorage.getItem('s2s_name') ?? '')
  const [role, setRole] = useState(() => localStorage.getItem('s2s_role') ?? '')
  const [roles, setRoles] = useState([])
  const [gemini, setGemini] = useState(null)

  useEffect(() => {
    api
      .getHealth()
      .then((h) => setGemini(Boolean(h.gemini_configured)))
      .catch(() => setGemini(false))
    api.getRoles().then((data) => setRoles(data.roles)).catch(() => {})
  }, [])

  function handleStart(event) {
    event.preventDefault()
    localStorage.setItem('s2s_name', name.trim())
    localStorage.setItem('s2s_role', role.trim())
    onStart()
  }

  return (
    <div className="min-h-screen">
      <BrandHeader
        right={
          <>
            {gemini !== null && (
              <Badge tone={gemini ? 'emerald' : 'amber'} className="hidden sm:inline-flex" title={gemini ? 'Questions and feedback powered by Google Gemini' : 'Add GEMINI_API_KEY in backend/.env to enable AI'}>
                <SparklesIcon className="h-3.5 w-3.5" />
                {gemini ? 'Gemini active' : 'Offline engine'}
              </Badge>
            )}
            <button
              type="button"
              onClick={onHistory}
              className="btn btn-secondary text-xs"
            >
              Past interviews
            </button>
          </>
        }
      />

      <main className="mx-auto max-w-6xl px-6">
        <section className="grid items-center gap-12 py-14 lg:grid-cols-2">
          <div>
            <Badge tone="brand">
              <BrainIcon className="h-3.5 w-3.5" />
              Professional mock-interview coach
            </Badge>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-5xl">
              Speak Better.
              <br />
              <span className="text-brand-600">Perform Better.</span>
            </h1>
            <p className="mt-4 max-w-md text-lg text-slate-600">
              Practice real interviews with an AI interviewer that listens to what you say{' '}
              <em>and</em> watches how you say it. Get a full Success Report with every session.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm font-medium text-slate-700">
              {[
                'Live webcam & microphone session in your browser',
                'Adaptive questions from Google Gemini',
                'Posture & eye-contact tracking as you answer',
              ].map((item) => (
                <li key={item} className="flex items-center gap-2.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                    <CheckIcon className="h-3 w-3" />
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <Card className="p-7">
            <h2 className="text-lg font-bold text-slate-900">Enter the Interview Room</h2>
            <p className="mt-1 text-sm text-slate-500">
              Resume-driven questions across three rounds: Managerial → Technical (with coding) → HR.{' '}
              {localStorage.getItem('s2s_parsed') ? 'Your resume profile is ready to reuse.' : ''}
            </p>

            <form onSubmit={handleStart}>
              <label className="label mt-5" htmlFor="s2s-name">
                Your name
              </label>
              <input
                id="s2s-name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Alex"
                className="input mt-1"
              />

              <label className="label mt-4" htmlFor="s2s-role">
                Target role
              </label>
              <input
                id="s2s-role"
                type="text"
                value={role}
                onChange={(event) => setRole(event.target.value)}
                placeholder="e.g. Frontend Engineer"
                list="s2s-roles"
                className="input mt-1"
              />
              <datalist id="s2s-roles">
                {roles.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>

              <button type="submit" className="btn-primary mt-6 w-full">
                Start mock interview
                <ArrowRightIcon className="h-4 w-4" />
              </button>
              <p className="mt-3 text-center text-xs text-slate-400">
                Next: upload your resume &amp; choose your coding round.
              </p>
            </form>
          </Card>
        </section>

        <section className="grid gap-6 pb-16 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} hover className="p-6">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <feature.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 font-bold text-slate-900">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.text}</p>
            </Card>
          ))}
        </section>
      </main>
    </div>
  )
}
