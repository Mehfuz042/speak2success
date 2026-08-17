import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import BrandHeader from '../components/BrandHeader.jsx'
import { Card, StatCard, EmptyState, Spinner } from '../components/ui.jsx'
import {
  BriefcaseIcon,
  ChevronRightIcon,
  TrashIcon,
  FileTextIcon,
  ChartIcon,
} from '../components/icons.jsx'

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

const STATUS_COLORS = {
  completed: 'bg-emerald-100 text-emerald-700',
  in_progress: 'bg-amber-100 text-amber-700',
}

export default function History({ onBack, onOpen }) {
  const [sessions, setSessions] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(null)

  useEffect(() => {
    api
      .listSessions()
      .then((data) => setSessions(data.sessions))
      .catch((err) => setError(err.message))
  }, [])

  async function handleDelete(id) {
    if (!window.confirm('Delete this interview? This cannot be undone.')) return
    setDeleting(id)
    try {
      await api.deleteSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(null)
    }
  }

  const completed = (sessions || []).filter((s) => s.overall_score != null)
  const avg = (values) =>
    values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
  const overallAvg = avg(completed.map((s) => s.overall_score))
  const categoryAverages = {}
  completed.forEach((s) => {
    Object.entries(s.category_breakdown || {}).forEach(([category, score]) => {
      categoryAverages[category] = categoryAverages[category] || []
      categoryAverages[category].push(score)
    })
  })

  return (
    <div className="min-h-screen bg-slate-50">
      <BrandHeader
        right={
          <button type="button" onClick={onOpen} className="btn btn-primary text-xs">
            New interview
          </button>
        }
      />

      <main className="mx-auto max-w-5xl px-6 py-8">
        <h1 className="text-2xl font-extrabold text-slate-900">Past interviews</h1>
        <p className="mt-1 text-sm text-slate-500">
          Review your Success Reports and watch your progress over time.
        </p>

        {error && <p className="mt-4 rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">{error}</p>}

        {sessions === null && !error && (
          <div className="mt-12 flex items-center justify-center gap-2 text-sm text-slate-400">
            <Spinner className="h-4 w-4" />
            Loading your interviews…
          </div>
        )}

        {sessions !== null && sessions.length === 0 && !error && (
          <div className="mt-8">
            <EmptyState
              icon={<FileTextIcon className="h-7 w-7" />}
              title="No interviews yet"
              body="Complete your first mock interview to see your Success Report here."
              action={
                <button type="button" onClick={onOpen} className="btn btn-primary">
                  Start a new interview
                  <ChevronRightIcon className="h-4 w-4" />
                </button>
              }
            />
          </div>
        )}

        {sessions && sessions.length > 0 && (
          <>
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              <StatCard
                label="Interviews"
                value={String(sessions?.length ?? 0)}
                icon={<BriefcaseIcon className="h-5 w-5" />}
              />
              <StatCard
                label="Completed"
                value={String(completed.length)}
                icon={<ChartIcon className="h-5 w-5" />}
              />
              <StatCard
                label="Average score"
                value={overallAvg != null ? overallAvg.toFixed(1) : '—'}
                icon={<ChartIcon className="h-5 w-5" />}
              />
            </div>

            {Object.keys(categoryAverages).length > 0 && (
              <Card className="mt-4 p-5">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Average by round</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {Object.entries(categoryAverages).map(([category, scores]) => {
                    const value = avg(scores)
                    return (
                      <div key={category} className="rounded-xl bg-slate-50 p-3">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-semibold text-slate-700">{category}</span>
                          <span className={`font-bold ${value >= 8 ? 'text-emerald-700' : value >= 6 ? 'text-amber-700' : 'text-rose-700'}`}>
                            {value.toFixed(1)}
                          </span>
                        </div>
                        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-200">
                          <div
                            className={`h-full rounded-full ${value >= 8 ? 'bg-emerald-500' : value >= 6 ? 'bg-amber-500' : 'bg-rose-500'}`}
                            style={{ width: `${Math.min(100, value * 10)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </Card>
            )}

            <ul className="mt-6 space-y-3">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-300"
                >
                  <button type="button" onClick={() => onOpen(s.id)} className="flex flex-1 items-center gap-4 text-left">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                      <FileTextIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-bold text-slate-800">
                        {s.role}
                        {s.name ? ` · ${s.name}` : ''}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {formatDate(s.created_at)} at {formatTime(s.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {s.overall_score != null ? (
                        <span className="text-2xl font-extrabold text-brand-600">
                          {s.overall_score}
                          <span className="text-xs font-semibold text-slate-400">/10</span>
                        </span>
                      ) : (
                        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${STATUS_COLORS[s.status] ?? 'bg-slate-100 text-slate-500'}`}>
                          {s.status === 'in_progress' ? 'In progress' : s.status}
                        </span>
                      )}
                      <ChevronRightIcon className="h-4 w-4 text-slate-300" />
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(s.id)}
                    disabled={deleting === s.id}
                    className="shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-rose-600 transition hover:bg-rose-50 disabled:opacity-50"
                    title="Delete this interview"
                  >
                    {deleting === s.id ? <Spinner className="h-4 w-4" /> : <TrashIcon className="h-4 w-4" />}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  )
}
