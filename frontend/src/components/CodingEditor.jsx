import { useState } from 'react'
import { api } from '../api/client.js'
import { Spinner } from './ui.jsx'
import { PlayIcon } from './icons.jsx'

export default function CodingEditor({ challenge, language, onSubmit }) {
  const [code, setCode] = useState(challenge.starter_code)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleRun() {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.runChallenge({
        challenge_id: challenge.challenge_id,
        language,
        code,
      })
      if (data.error) setError(data.error + (data.details ? ` — ${data.details}` : ''))
      else setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  function handleSubmit() {
    onSubmit(code, result)
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {challenge.title} · {challenge.difficulty}
        </span>
        <span className="text-xs font-medium text-slate-500">{language}</span>
      </div>

      <div className="grid gap-0 md:grid-cols-2">
        <div className="border-b border-slate-200 p-4 md:border-b-0 md:border-r">
          <p className="text-sm text-slate-700">{challenge.prompt}</p>
          <div className="mt-3 space-y-1 rounded-lg bg-slate-100 p-3 font-mono text-xs text-slate-600">
            {challenge.samples?.map((sample, i) => (
              <div key={i}>
                <div>
                  <span className="text-slate-400">in&nbsp;&nbsp;</span>
                  {sample.input}
                </div>
                <div>
                  <span className="text-slate-400">out&nbsp;</span>
                  {sample.output}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col">
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            rows={10}
            className="w-full flex-1 resize-none bg-slate-950 p-4 font-mono text-sm text-emerald-100 focus:outline-none focus-visible:ring-0 min-h-[220px]"
          />
          <div className="flex items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2">
            <div className="min-w-0 flex-1">
              {error && <span className="text-xs text-rose-600">{error}</span>}
              {result && !error && (
                <span className="text-xs font-semibold text-slate-700">
                  {result.passed}/{result.total} tests passed · {result.score_percent}%
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleRun}
              disabled={running}
              className="btn rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {running ? (
                <>
                  <Spinner className="mr-1.5 inline h-3.5 w-3.5" />
                  Running…
                </>
              ) : (
                <>
                  <PlayIcon className="mr-1.5 inline h-3.5 w-3.5" />
                  Run tests
                </>
              )}
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={running || !result}
              className="btn rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Submit solution
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
