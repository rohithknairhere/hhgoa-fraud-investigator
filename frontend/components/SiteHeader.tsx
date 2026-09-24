import Link from "next/link";

const NAV = [
  { href: "/", label: "Case inbox" },
  { href: "/#how-it-works", label: "How it works" },
];

export function SiteHeader() {
  return (
    <header className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
      <div className="neu flex flex-wrap items-center justify-between gap-4 px-5 py-4">
        <Link href="/" className="focus-ring flex items-center gap-3 rounded-xl" aria-label="HHGOA Fraud Investigator home">
          <span aria-hidden="true" className="neu-sm grid h-10 w-10 place-items-center">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none">
              <path d="M12 12 5 6M12 12l7-6M12 12l-6 7M12 12l6 7" stroke="#3730a3" strokeWidth="1.8" strokeLinecap="round" />
              <circle cx="5" cy="6" r="2.2" fill="#1e293b" />
              <circle cx="19" cy="6" r="2.2" fill="#1e293b" />
              <circle cx="6" cy="19" r="2.2" fill="#1e293b" />
              <circle cx="18" cy="19" r="2.2" fill="#9f1239" />
              <circle cx="12" cy="12" r="3.2" fill="#3730a3" />
            </svg>
          </span>
          <span className="leading-tight">
            <span className="block text-base font-bold text-ink">HHGOA Fraud Investigator</span>
            <span className="block text-xs font-medium text-ink-muted">TigerGraph, MCP and LangGraph</span>
          </span>
        </Link>
        <nav aria-label="Primary">
          <ul className="flex flex-wrap gap-3 text-sm font-semibold">
            {NAV.map((n) => (
              <li key={n.href}>
                <Link href={n.href} className="focus-ring neu-sm block px-4 py-2 text-ink hover:shadow-neu">
                  {n.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
