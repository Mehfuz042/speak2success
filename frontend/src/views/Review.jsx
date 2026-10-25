import { api } from '../api/client.js'
import BrandHeader from '../components/BrandHeader.jsx'
import { Badge, Card } from '../components/ui.jsx'
import {
  CheckIcon,
  XIcon,
  PrintIcon,
  ArrowRightIcon,
  BrainIcon,
  EyeIcon,
  SmileIcon,
  ClockIcon,
  ChartIcon,
} from '../components/icons.jsx'

const CATEGORY_COLORS = {
  Managerial: 'bg-amber-500',
  Technical: 'bg-brand-600',
  Coding: 'bg-emerald-600',
  HR: 'bg-sky-500',
}

const colorFor = (score) =>
  score == null
    ? 'text-slate-400'
    : score >= 8
      ? 'text-emerald-700'
      : score >= 6
        ? 'text-amber-700'
        : 'text-rose-700'

const barFor = (score) =>
  score >= 8 ? 'bg-emerald-500' : score >= 6 ? 'bg-amber-500' : 'bg-rose-500'

function ScoreBadge({ score }) {
  if (score == null) {
    return (
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500">
        Not answered
      </span>
    )
  }
  return (
    <span className={`text-lg font-extrabold ${colorFor(score)}`}>
      {score}
      <span className="text-xs font-semibold text-slate-400">/10</span>
    </span>
  )
}

function MetricTile({ label, value, suffix = '', tone }) {
  return (
    <div className="rounded-lg bg-white px-2.5 py-2 ring-1 ring-slate-100">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-0.5 text-sm font-bold ${tone ?? 'text-slate-700'}`}>
        {value != null ? `${Math.round(value)}${suffix}` : '—'}
      </p>
    </div>
  )
}

function ConfidenceMeter({ confidence }) {
  if (!confidence || confidence.score == null) return null
  const pct = confidence.pct ?? confidence.score * 10
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">Confidence</span>
        <span className="font-bold text-slate-800">
          {confidence.score}/10 · {confidence.level}
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full ${barFor(confidence.score)}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  )
}

function groupRows(rows) {
  const groups = []
  const index = new Map()
  for (const row of rows) {
    const name = row.round_name || `${row.category || 'Technical'} Round`
    if (!index.has(name)) {
      index.set(name, [])
      groups.push([name, index.get(name)])
    }
    index.get(name).push(row)
  }
  return groups
}

function QuestionCard({ row, index, session }) {
  const body = row.body_language
  const confidence = row.confidence || body?.confidence
  const metrics = body?.metrics || {}
  const speech = row.speech && typeof row.speech === 'object' ? row.speech : null
  const wpm = typeof row.speech === 'number' ? row.speech : speech?.words_per_minute
  const coding = row.coding || (
    row.passed != null ? { passed: row.passed, total: row.total } : null
  )
  const strengths = row.strengths || []
  const improvements = row.improvements || (row.top_suggestion ? [row.top_suggestion] : [])

  return (
    <div
      className={`rounded-2xl border bg-white p-4 shadow-sm ${
        row.answered ? 'border-slate-200' : 'border-dashed border-slate-300 bg-slate-50/60'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-[11px] font-bold text-white">
            {row.question_number ?? index + 1}
          </span>
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-600">
            {row.category || 'General'}
          </span>
          {row.difficulty && (
            <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              {row.difficulty}
            </span>
          )}
          {row.type === 'coding' && (
            <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
              Coding · {row.language || 'python'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {row.verdict && (
            <span className={`text-[11px] font-semibold ${row.answered ? colorFor(row.score) : 'text-slate-400'}`}>
              {row.verdict}
            </span>
          )}
          <ScoreBadge score={row.score} />
        </div>
      </div>

      <p className="mt-2 text-sm font-semibold leading-relaxed text-slate-900">{row.question}</p>

      {!row.answered ? (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          You skipped this question. {improvements[0]}
        </p>
      ) : (
        <>
          {row.answer && (
            <details className="group mt-2">
              <summary className="cursor-pointer list-none text-xs font-semibold text-brand-700">
                <span className="group-open:hidden">▸ Show your answer</span>
                <span className="hidden group-open:inline">▾ Hide your answer</span>
              </summary>
              <p className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
                {row.answer}
              </p>
            </details>
          )}

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl bg-emerald-50/70 p-3">
              <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-emerald-700">
                <CheckIcon className="h-3.5 w-3.5" />
                What went well
              </p>
              {strengths.length ? (
                <ul className="mt-1.5 space-y-1">
                  {strengths.map((s) => (
                    <li key={s} className="flex gap-2 text-xs text-emerald-900">
                      <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-xs text-emerald-800">No specific strength flagged for this answer.</p>
              )}
            </div>

            <div className="rounded-xl bg-rose-50/70 p-3">
              <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-rose-700">
                <XIcon className="h-3.5 w-3.5" />
                Improve next time
              </p>
              {improvements.length ? (
                <ul className="mt-1.5 space-y-1">
                  {improvements.slice(0, 6).map((s) => (
                    <li key={s} className="flex gap-2 text-xs text-rose-900">
                      <XIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-xs text-rose-800">No specific improvement generated.</p>
              )}
            </div>
          </div>

          {coding && coding.passed != null && (
            <div className="mt-3 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-800">
              <span className="font-bold">Hidden tests:</span> {coding.passed}/{coding.total} passed
              {coding.score_percent != null ? ` · ${coding.score_percent}%` : ''}
            </div>
          )}

          <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50 p-3">
            <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
              Delivery · speech, body language &amp; confidence
            </p>

            {confidence ? (
              <div className="mt-2">
                <ConfidenceMeter confidence={confidence} />
              </div>
            ) : (
              <p className="mt-1 text-xs text-slate-500">
                No camera data for this answer — body language and confidence could not be assessed.
              </p>
            )}

            {(body?.score != null || Object.keys(metrics).length > 0) && (
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                <MetricTile label="Body language" value={body?.score} suffix="/10" />
                <MetricTile label="Eye contact" value={metrics.eye_contact_pct} suffix="%" />
                <MetricTile label="Smiling" value={metrics.smile_pct} suffix="%" />
                <MetricTile label="Head steady" value={metrics.head_steady_pct} suffix="%" />
                <MetricTile label="Face visible" value={metrics.face_present_pct} suffix="%" />
                <MetricTile label="Blink rate" value={metrics.blink_rate_per_min} suffix="/min" />
              </div>
            )}

            {(wpm != null || speech) && (
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                <MetricTile label="Speaking pace" value={wpm} suffix=" WPM" />
                <MetricTile label="Clarity" value={speech?.clarity_score} suffix="/10" />
                <MetricTile label="Filler words" value={speech?.total_filler_words} />
              </div>
            )}

            {!speech && wpm == null && !confidence && (
              <p className="mt-2 text-xs text-slate-500">
                Speak your answer (rather than typing) with the camera on to get full delivery feedback.
              </p>
            )}

            {(body?.suggestions?.length > 0 || speech?.suggestions?.length > 0) && (
              <ul className="mt-2 space-y-1">
                {[...(body?.suggestions || []), ...(speech?.suggestions || [])].slice(0, 4).map((s) => (
                  <li key={s} className="text-xs text-slate-600">
                    • {s}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {row.has_audio && row.answer_id && session?.id && (
            <audio
              controls
              preload="none"
              src={api.answerAudioUrl(session.id, row.answer_id)}
              className="mt-3 h-9 w-full"
            >
              Your browser doesn't support audio playback.
            </audio>
          )}
        </>
      )}
    </div>
  )
}

export default function Review({ review, session, onExit, onRestart }) {
  if (!review) return null

  const breakdown = review.category_breakdown || {}
  const rows = review.answer_feedback || []
  const groups = groupRows(rows)
  const total = review.questions_total ?? rows.length
  const answered = review.questions_answered ?? rows.filter((r) => r.answered).length
  const skipped = review.questions_skipped ?? Math.max(0, total - answered)
  const bodyLanguage = review.body_language
  const confidence = review.confidence || bodyLanguage?.confidence

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
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-600">
              {answered}/{total} questions answered
            </span>
            {skipped > 0 && (
              <span className="rounded-full bg-amber-100 px-3 py-1 font-semibold text-amber-700">
                {skipped} skipped
              </span>
            )}
            {confidence?.score != null && (
              <span className="rounded-full bg-emerald-100 px-3 py-1 font-semibold text-emerald-700">
                Confidence {confidence.score}/10 · {confidence.level}
              </span>
            )}
            {bodyLanguage?.score != null && (
              <span className="rounded-full bg-sky-100 px-3 py-1 font-semibold text-sky-700">
                Body language {bodyLanguage.score}/10
              </span>
            )}
          </div>
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
              {!Object.keys(breakdown).length && (
                <p className="text-sm text-slate-500">No answers were submitted.</p>
              )}
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-bold text-slate-900">
              <EyeIcon className="h-4 w-4 text-brand-600" />
              Body language &amp; confidence
            </h2>
            <div className="flex items-center gap-4">
              {confidence?.score != null && (
                <span className="text-sm font-semibold text-slate-600">
                  Confidence{' '}
                  <span className={`text-xl font-extrabold ${colorFor(confidence.score)}`}>
                    {confidence.score}
                  </span>
                  <span className="text-xs font-semibold text-slate-400">/10 · {confidence.level}</span>
                </span>
              )}
              {bodyLanguage?.score != null && (
                <span className={`text-2xl font-extrabold ${colorFor(bodyLanguage.score)}`}>
                  {bodyLanguage.score}
                  <span className="text-sm font-semibold text-slate-400">/10</span>
                </span>
              )}
            </div>
          </div>

          {bodyLanguage ? (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
                <MetricTile label="Confidence" value={confidence?.pct} suffix="%" />
                <MetricTile label="Eye contact" value={bodyLanguage.metrics?.eye_contact_pct} suffix="%" />
                <MetricTile label="Smiling" value={bodyLanguage.metrics?.smile_pct} suffix="%" />
                <MetricTile label="Head steady" value={bodyLanguage.metrics?.head_steady_pct} suffix="%" />
                <MetricTile label="Face present" value={bodyLanguage.metrics?.face_present_pct} suffix="%" />
                <MetricTile label="Blink rate" value={bodyLanguage.metrics?.blink_rate_per_min} suffix="/min" />
                <MetricTile label="Posture shifts" value={bodyLanguage.metrics?.posture_shift_count} />
              </div>
              {confidence?.answers_assessed != null && (
                <p className="mt-3 text-sm text-slate-600">
                  <span className="font-semibold text-slate-800">Confidence levels: </span>
                  {confidence.confident_answers || 0} confident · {confidence.composed_answers || 0} composed ·{' '}
                  {confidence.nervous_answers || 0} nervous ({confidence.answers_assessed} answer
                  {confidence.answers_assessed === 1 ? '' : 's'} analysed)
                </p>
              )}
              {bodyLanguage.suggestions?.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {bodyLanguage.suggestions.map((s) => (
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
              No camera data was captured — enable your webcam during the interview to unlock
              body-language and confidence coaching. Questions answered without the camera are marked
              below.
            </p>
          )}
        </Card>

        <section className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-extrabold text-slate-900">Question-by-question feedback</h2>
              <p className="mt-1 text-sm text-slate-500">
                Every question is reviewed below — including your answer, body language, confidence and
                speech for each one. Skipped questions are marked so you know exactly what to practise.
              </p>
            </div>
            <Badge tone={skipped ? 'amber' : 'emerald'}>
              {answered}/{total} answered
            </Badge>
          </div>

          {groups.length === 0 && (
            <Card className="mt-4 p-6 text-sm text-slate-500">No questions were recorded.</Card>
          )}

          {groups.map(([roundName, items]) => (
            <div key={roundName} className="mt-5">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold uppercase tracking-wide text-slate-500">{roundName}</h3>
                <span className="text-xs font-semibold text-slate-400">
                  {items.filter((r) => r.answered).length}/{items.length} answered
                </span>
              </div>
              <div className="mt-2 space-y-3">
                {items.map((row, index) => (
                  <QuestionCard
                    key={`${row.round_id || roundName}-${row.question_number ?? index}-${index}`}
                    row={row}
                    index={index}
                    session={session}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>

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
                      className={`h-full rounded-full ${barFor(trait.score)}`}
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

        <Card className="mt-6 p-6">
          <h2 className="flex items-center gap-2 font-bold text-slate-900">
            <ChartIcon className="h-4 w-4 text-brand-600" />
            Coach's next steps
          </h2>
          <ul className="mt-3 space-y-3">
            {(review.action_plan || []).map((step, i) => (
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

        <button
          type="button"
          onClick={onRestart}
          className="btn btn-primary mt-8 w-full py-4 text-base"
        >
          Practice again with a new interview
          <ArrowRightIcon className="h-5 w-5" />
        </button>
        <p className="mt-2 text-center text-xs text-slate-400">
          Powered by {review.source === 'gemini' ? 'Google Gemini' : 'the built-in coaching engine'} · body
          language analysed on-device with MediaPipe
        </p>
      </main>
    </div>
  )
}
