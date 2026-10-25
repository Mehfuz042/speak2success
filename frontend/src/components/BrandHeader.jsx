export default function BrandHeader({ right }) {
  return (
    <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <a href="#/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 shadow-sm">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
              <path d="M12 3a4 4 0 0 0-4 4v4a4 4 0 0 0 8 0V7a4 4 0 0 0-4-4Z" />
              <path d="M6 10a6 6 0 0 0 12 0M12 16v3M8.5 19h7" />
            </svg>
          </span>
          <span className="text-lg font-extrabold tracking-tight text-slate-900">
            Speak<span className="text-brand-600">2Success</span>
          </span>
        </a>
        <div className="flex items-center gap-2">{right}</div>
      </div>
    </header>
  )
}
