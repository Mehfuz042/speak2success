export function Spinner({ className = 'h-4 w-4' }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`}>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}

export function Badge({ children, tone = 'slate', className = '' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-600',
    brand: 'bg-brand-50 text-brand-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-amber-50 text-amber-700',
    rose: 'bg-rose-50 text-rose-700',
  }
  return (
    <span className={`chip ${tones[tone] || tones.slate} ${className}`}>{children}</span>
  )
}

export function Card({ children, className = '', hover = false }) {
  return <div className={`card ${hover ? 'card-hover' : ''} ${className}`}>{children}</div>
}

export function StatCard({ label, value, icon, accent = 'text-brand-600' }) {
  return (
    <Card className="p-5 text-center">
      {icon && <div className={`mx-auto mb-2 flex h-10 w-10 items-center justify-center ${accent}`}>{icon}</div>}
      <p className="text-3xl font-extrabold tracking-tight text-slate-900">{value}</p>
      <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
    </Card>
  )
}

export function EmptyState({ icon, title, body, action }) {
  return (
    <Card className="p-12 text-center">
      {icon && <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">{icon}</div>}
      <p className="mt-4 text-lg font-bold text-slate-800">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">{body}</p>}
      {action && <div className="mt-6">{action}</div>}
    </Card>
  )
}

export function SectionLabel({ children }) {
  return (
    <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{children}</p>
  )
}
