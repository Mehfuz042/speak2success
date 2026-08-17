import { api } from '../api/client.js'
import BrandHeader from '../components/BrandHeader.jsx'
import { Badge, Card } from '../components/ui.jsx'
import { CheckIcon, XIcon, PrintIcon, ArrowRightIcon, BrainIcon } from '../components/icons.jsx'

const CATEGORY_COLORS = {
  Managerial: 'bg-amber-500',
  Technical: 'bg-brand-600',
  Coding: 'bg-emerald-600',
  HR: 'bg-sky-500',
}

export default function Review({ review, session, onExit, onRestart }) {
  if (!review) return null

  const breakdown = review.category_breakdown || {}
  const colorFor = (score) =>
    score >= 8 ? 'text-emerald-700' : score >= 6 ? 'text-amber-700' : 'text-rose-700'

  return (
    <div className="min-h-screen">
      <BrandHeader
        right={
          <>
            <button
              type="button"
              onClick={() => window.print()}
              className="btn btn-secondary text-xs no-print"
              title="Print or save this report as a PDF"
            >
              <PrintIcon className="h-4 w-4" />
              Print / PDF
            </button>
            <button type="button" onClick={onRestart} className="btn btn-primary text-xs no-print">
              New interview
            </button>
          </>
        }
      />

      <main className="mx-auto max-w-5xl px-6 pb-16">
        <section className="card p-8 text-center">
          <Badge tone="brand">
            <BrainIcon className="h-3.5 w-3.5" />
            Success Report
          </Badge>
          <h1 className="mt-3 text-2xl font-extrabold text-slate-900">{session?.role}</h1>
          <div className="mx-auto mt-6 flex h-28 w-28 flex-col items-center justify-center rounded-full bg-brand-600 text-white shadow-lg">
            <span className="text-4xl font-extrabold">{review.overall_score}</span>
            <span className="text-xs font-medium opacity-80">/ 10 overall</span>
          </div>
          <p className="mx-auto mt-6 max-w-2xl text-slate-700">{review.verdict}</p>
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card className="p-6">
            <h2 className="font-bold text-slate-900">Category breakdown</h2>
            <div className="mt-4 space-y-4">
              {Object.entries(breakdown).map(([category, score]) => (
                <div key={category}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-700">{category}</span>
                    <span className={`font-bold ${colorFor(score)}`}>{score}/10</span>
                  </div>
                  <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full ${CATEGORY_COLORS[category] || 'bg-slate-400'}`}
                      style={{ width: `${Math.min(100, score * 10)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-6">
            <Card className="p-6">
              <h2 className="font-bold text-emerald-700">Strengths</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {(review.strengths?.length ? review.strengths : ['—']).map((s) => (
                  <li key={s} className="flex gap-2.5">
                    <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-6">
              <h2 className="font-bold text-rose-700">Weaknesses</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {(review.weaknesses?.length ? review.weaknesses : ['None flagged — great session!']).map((s) => (
                  <li key={s} className="flex gap-2.5">
                    <XIcon className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </section>

        <Card className="mt-6 p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-slate-900">Body language</h2>
            {review.body_language?.score != null && (
              <span className={`text-2xl font-extrabold ${colorFor(review.body_language.score)}`}>
                {review.body_language.score}
                <span className="text-sm font-semibold text-slate-400">/10</span>
              </span>
            )}
          </div>
          {review.body_language ? (
            <>
              <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                {[
                  ['Confidence', review.body_language.confidence?.pct, '%'],
                  ['Eye contact', review.body_language.metrics?.eye_contact_pct, '%'],
                  ['Smiling', review.body_language.metrics?.smile_pct, '%'],
                  ['Head steady', review.body_language.metrics?.head_steady_pct, '%'],
                  ['Face present', review.body_language.metrics?.face_present_pct, '%'],
                  ['Blink rate', review.body_language.metrics?.blink_rate_per_min, '/min'],
                ].map(([label, value, suffix]) => (
                  <div key={label} className="rounded-xl bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-extrabold text-slate-800">
                      {value != null ? `${value}${suffix}` : '—'}
                    </p>
                  </div>
                ))}
              </div>
              {review.body_language.confidence?.level && (
                <p className="mt-3 text-sm text-slate-600">
                  <span className="font-semibold text-slate-800">Confidence level: </span>
                  {review.body_language.confidence.level}
                </p>
              )}
              {review.body_language.suggestions?.length > 0 && (
                <ul className="mt-4 space-y-1.5">
                  {review.body_language.suggestions.map((s) => (
                    <li key={s} className="flex gap-2 text-sm text-slate-600">
                      <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="mt-3 text-sm text-slate-500">
              No camera data was captured — enable your webcam during the interview to unlock body-language coaching.
            </p>
          )}
        </Card>

        {review.mindset && (
          <Card className="mt-6 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-900">Mindset Profile</h2>
              <span className={`text-2xl font-extrabold ${colorFor(review.mindset.overall_score)}`}>
                {review.mindset.overall_score}
                <span className="text-sm font-semibold text-slate-400">/10</span>
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Analysis of your communication style, problem-solving approach, and professional traits.
            </p>

            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Object.entries(review.mindset.traits || {}).map(([traitId, trait]) => (
                <div key={traitId} className="rounded-xl bg-slate-50 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{trait.label}</p>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className={`text-xl font-extrabold ${colorFor(trait.score)}`}>{trait.score}</span>
                    <span className="text-xs text-slate-400">/10</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className={`h-full rounded-full ${trait.score >= 7 ? 'bg-emerald-500' : trait.score >= 5 ? 'bg-amber-500' : 'bg-rose-500'}`}
                      style={{ width: `${Math.min(100, trait.score * 10)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {review.mindset.dominant_traits?.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Dominant Traits</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {review.mindset.dominant_traits.map((t) => (
                    <span key={t} className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {review.mindset.growth_areas?.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Growth Areas</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {review.mindset.growth_areas.map((t) => (
                    <span key={t} className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {review.mindset.suggestions?.length > 0 && (
              <ul className="mt-4 space-y-1.5">
                {review.mindset.suggestions.map((s) => (
                  <li key={s} className="flex gap-2 text-sm text-slate-600">
                    <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card className="p-6">
            <h2 className="font-bold text-slate-900">Coach's next steps</h2>
            <ul className="mt-3 space-y-3">
              {review.action_plan?.map((step, i) => (
                <li key={step} className="flex gap-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
                    {i + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
            {review.suggestions?.map((s) => (
              <p key={s} className="mt-2 text-xs text-slate-500">
                • {s}
              </p>
            ))}
          </Card>

          <Card className="p-6">
            <h2 className="font-bold text-slate-900">Answer highlights</h2>
            <div className="mt-3 max-h-80 space-y-3 overflow-y-auto pr-1">
              {review.answer_feedback?.map((a) => (
                <div key={`${a.category}-${a.question}`} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-white px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-500 ring-1 ring-slate-200">
                      {a.category}
                    </span>
                    <span className={`text-sm font-bold ${colorFor(a.score)}`}>{a.score}/10</span>
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-slate-800">{a.question}</p>
                  {a.type === 'coding' && a.passed != null && (
                    <p className="mt-1 text-xs font-semibold text-emerald-700">
                      Hidden tests {a.passed}/{a.total} passed
                    </p>
                  )}
                  {a.top_suggestion && (
                    <p className="mt-1 text-xs text-slate-500">{a.top_suggestion}</p>
                  )}
                  {a.speech != null && (
                    <p className="mt-1 text-[10px] text-slate-400">{a.speech} WPM speaking pace</p>
                  )}
                  {a.has_audio && a.answer_id && (
                    <audio
                      controls
                      preload="none"
                      src={api.answerAudioUrl(session?.id, a.answer_id)}
                      className="mt-2 h-8 w-full"
                    >
                      Your browser doesn't support audio playback.
                    </audio>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </section>

        <button
          type="button"
          onClick={onRestart}
          className="btn btn-primary mt-8 w-full py-4 text-base"
        >
          Practice again with a new interview
          <ArrowRightIcon className="h-5 w-5" />
        </button>
        <p className="mt-2 text-center text-xs text-slate-400">
          Powered by {review.source === 'gemini' ? 'Google Gemini' : 'the built-in coaching engine'} · add your Gemini
          API key in backend/.env for AI-written reports
        </p>
      </main>
    </div>
  )
}
