import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'
import BrandHeader from '../components/BrandHeader.jsx'
import { Card, SectionLabel, Spinner } from '../components/ui.jsx'
import { ArrowLeftIcon, ArrowRightIcon, FileTextIcon, UploadIcon } from '../components/icons.jsx'

const DIFFICULTIES = ['Easy', 'Medium', 'Hard']
const LANGUAGES_FALLBACK = [
  { id: 'python', name: 'Python' },
  { id: 'javascript', name: 'JavaScript' },
  { id: 'java', name: 'Java' },
  { id: 'cpp', name: 'C++' },
]

function field(label, value, onChange, placeholder, list, id) {
  return (
    <label className="label" htmlFor={id}>
      {label}
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        list={list}
        className="input mt-1"
      />
    </label>
  )
}

function selectField(label, value, onChange, options, id) {
  return (
    <label className="label" htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="input mt-1">
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function Setup({ onStart, onBack }) {
  const [file, setFile] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [parsed, setParsed] = useState(null)
  const [parseError, setParseError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const [name, setName] = useState(() => localStorage.getItem('s2s_name') ?? '')
  const [role, setRole] = useState(() => localStorage.getItem('s2s_role') ?? 'Software Engineer')
  const [languages, setLanguages] = useState(LANGUAGES_FALLBACK)
  const [roles, setRoles] = useState([])
  const [language, setLanguage] = useState('python')
  const [difficulty, setDifficulty] = useState('Easy')
  const [codingCount, setCodingCount] = useState(2)
  const [counts, setCounts] = useState({ managerial: 3, technical: 3, hr: 3, language: 2 })
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getLanguages().then((data) => setLanguages(data.languages)).catch(() => {})
    api.getRoles().then((data) => setRoles(data.roles)).catch(() => {})
  }, [])

  const handleParse = useCallback(
    async (chosen) => {
      if (!chosen) return
      setParsing(true)
      setParseError(null)
      setParsed(null)
      try {
        const data = await api.parseResume(chosen)
        setParsed(data)
        if (data.suggested_roles?.length) setRole(data.suggested_roles[0])
        localStorage.setItem('s2s_parsed', JSON.stringify(data))
      } catch (err) {
        setParseError(err.message)
      } finally {
        setParsing(false)
      }
    },
    [],
  )

  const setCount = (key) => (value) => setCounts((prev) => ({ ...prev, [key]: value }))

  const handleStart = async () => {
    if (!role.trim()) {
      setError('Enter a target role to continue.')
      return
    }
    setStarting(true)
    setError(null)
    localStorage.setItem('s2s_name', name.trim())
    localStorage.setItem('s2s_role', role.trim())
    try {
      const payload = {
        user_id: 'guest',
        name: name.trim(),
        role: role.trim(),
        skills: parsed ? Object.values(parsed.skills).flat() : [],
        experience_years: parsed?.experience_years ?? 0,
        resume_summary: parsed ? { suggested_roles: parsed.suggested_roles } : undefined,
        coding_language: language,
        difficulty,
        coding_count: codingCount,
        managerial_count: counts.managerial,
        technical_count: counts.technical,
        hr_count: counts.hr,
        language_count: counts.language,
      }
      const data = await api.createSession(payload)
      onStart(data.session)
    } catch (err) {
      setError(err.message)
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="min-h-screen">
      <BrandHeader
        right={
          <button type="button" onClick={onBack} className="btn btn-ghost text-sm">
            <ArrowLeftIcon className="h-4 w-4" />
            Back
          </button>
        }
      />

      <main className="mx-auto max-w-5xl px-6 pb-16">
        <div className="pt-8">
          <SectionLabel>Session setup</SectionLabel>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Set up your professional interview
          </h1>
          <p className="mt-1 text-slate-600">
            Three rounds · Managerial → Technical (theory + coding) → HR
          </p>
        </div>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <Card className="p-6">
            <h2 className="font-bold text-slate-900">1 · Resume (recommended)</h2>
            <p className="mt-1 text-sm text-slate-500">
              Upload a PDF or TXT so questions are tailored to your profile.
            </p>

            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const dropped = e.dataTransfer.files?.[0]
                if (dropped) {
                  setFile(dropped)
                  handleParse(dropped)
                }
              }}
              className={`mt-4 flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 transition ${
                dragOver ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-brand-400'
              }`}
            >
              {parsing ? (
                <Spinner className="h-6 w-6 text-brand-600" />
              ) : file ? (
                <FileTextIcon className="h-8 w-8 text-brand-600" />
              ) : (
                <UploadIcon className="h-8 w-8 text-slate-400" />
              )}
              <span className="mt-3 text-sm font-semibold text-slate-700">
                {file ? file.name : 'Click or drop your resume here'}
              </span>
              <span className="mt-1 text-xs text-slate-400">
                {parsing ? 'Parsing with Gemini…' : 'PDF or TXT · up to 8 MB'}
              </span>
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const chosen = e.target.files?.[0]
                if (chosen) {
                  setFile(chosen)
                  handleParse(chosen)
                }
              }}
            />

            {parseError && (
              <p className="mt-3 rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">{parseError}</p>
            )}
            {parsed && (
              <div className="mt-4 space-y-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Suggested roles
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {parsed.suggested_roles.map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => setRole(r)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                          role === r
                            ? 'bg-brand-600 text-white'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Skills</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.values(parsed.skills).flat().slice(0, 20).map((s) => (
                      <span key={s} className="rounded bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                        {s}
                      </span>
                    ))}
                  </div>
                  {parsed.experience_years > 0 && (
                    <p className="mt-2 text-xs text-slate-500">
                      ~{parsed.experience_years} year{parsed.experience_years > 1 ? 's' : ''} of experience detected
                    </p>
                  )}
                </div>
              </div>
            )}
          </Card>

          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="font-bold text-slate-900">2 · Candidate</h2>
              <div className="mt-4 space-y-4">
                {field('Your name', name, setName, 'e.g. Alex', undefined, 's2s-setup-name')}
                {field('Target role', role, setRole, 'e.g. Full Stack Developer', 's2s-roles', 's2s-setup-role')}
                <datalist id="s2s-roles">
                  {roles.map((r) => (
                    <option key={r} value={r} />
                  ))}
                </datalist>
                <p className="text-xs text-slate-400">
                  {roles.length > 0
                    ? `${roles.length} roles are fully supported — pick one, or type any role you like.`
                    : 'Any role works; supported roles get tailored questions.'}
                </p>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="font-bold text-slate-900">3 · Coding round</h2>
              <p className="mt-1 text-sm text-slate-500">
                Coding problems (with hidden test cases) appear in the Technical round.
              </p>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {selectField(
                  'Language',
                  language,
                  setLanguage,
                  languages.map((l) => ({ value: l.id, label: l.name })),
                  's2s-setup-lang',
                )}
                {selectField(
                  'Difficulty',
                  difficulty,
                  setDifficulty,
                  DIFFICULTIES.map((d) => ({ value: d, label: d })),
                  's2s-setup-diff',
                )}
                {selectField(
                  'Problems',
                  String(codingCount),
                  (v) => setCodingCount(Number(v)),
                  [1, 2, 3].map((n) => ({ value: String(n), label: String(n) })),
                  's2s-setup-problems',
                )}
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="font-bold text-slate-900">4 · Questions per round</h2>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { key: 'managerial', label: 'Managerial' },
                  { key: 'technical', label: 'Technical' },
                  { key: 'hr', label: 'HR' },
                  { key: 'language', label: 'Language theory' },
                ].map(({ key, label }) =>
                  selectField(
                    label,
                    counts[key],
                    setCount(key),
                    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => ({ value: String(n), label: String(n) })),
                    `s2s-setup-${key}`,
                  ),
                )}
              </div>
            </Card>
          </div>
        </section>

        {error && <p className="mt-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}

        <button
          type="button"
          onClick={handleStart}
          disabled={starting}
          className="btn-primary mt-6 w-full py-4 text-base"
        >
          {starting ? (
            <>
              <Spinner className="h-5 w-5" />
              Preparing your interview…
            </>
          ) : (
            <>
              Start professional interview
              <ArrowRightIcon className="h-5 w-5" />
            </>
          )}
        </button>
        <p className="mt-2 text-center text-xs text-slate-400">
          You'll need camera &amp; microphone access in the interview room.
        </p>
      </main>
    </div>
  )
}
