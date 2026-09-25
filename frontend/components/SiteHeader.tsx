import Link from "next/link";

const NAV = [
  { href: "/", label: "Cases" },
  { href: "/#how-it-works", label: "How it works" },
];

export function SiteHeader() {
  return (
    <header className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl bg-deep px-5 py-4 shadow-neu">
        <Link href="/" className="focus-ring flex items-center gap-3 rounded-xl" aria-label="HHGOA Fraud Desk home">
          <span aria-hidden="true" className="grid h-10 w-10 place-items-center rounded-2xl bg-night">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none">
              <path d="M12 12 5 6M12 12l7-6M12 12l-6 7M12 12l6 7" stroke="#39a8ad" strokeWidth="1.8" strokeLinecap="round" />
              <circle cx="5" cy="6" r="2.2" fill="#f7f7f8" />
              <circle cx="19" cy="6" r="2.2" fill="#f7f7f8" />
              <circle cx="6" cy="19" r="2.2" fill="#f7f7f8" />
              <circle cx="18" cy="19" r="2.2" fill="#ff6b6b" />
              <circle cx="12" cy="12" r="3.2" fill="#73ffff" />
            </svg>
          </span>
          <span className="leading-tight">
            <span className="block text-base font-bold text-white">HHGOA Fraud Desk</span>
            <span className="block text-xs font-medium text-aqua">Fraud cases on TigerGraph</span>
          </span>
        </Link>
        <nav aria-label="Primary">
          <ul className="flex flex-wrap gap-2 text-sm font-semibold">
            {NAV.map((n) => (
              <li key={n.href}>
                <Link
                  href={n.href}
                  className="focus-ring block rounded-2xl px-4 py-2 text-white transition-colors hover:bg-white/10 hover:text-aqua"
                >
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
