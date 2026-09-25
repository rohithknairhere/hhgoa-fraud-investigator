import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mx-auto w-full max-w-7xl px-4 pb-28 sm:px-6 lg:px-8">
      <div className="neu-sm flex flex-col gap-3 px-5 py-4 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          Built for Hacker House Goa on the HHGOA IEEE-CIS dataset. The data is anonymised; no real cardholders.
        </p>
        <nav aria-label="Legal">
          <ul className="flex gap-4 font-semibold">
            <li>
              <Link href="/privacy-policy" className="focus-ring rounded text-ink underline-offset-4 hover:underline">
                Privacy policy
              </Link>
            </li>
            <li>
              <Link href="/terms-and-conditions" className="focus-ring rounded text-ink underline-offset-4 hover:underline">
                Terms &amp; conditions
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}
