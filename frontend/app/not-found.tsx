import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <section className="neu mx-auto flex max-w-xl flex-col items-center gap-6 p-10 text-center" aria-labelledby="nf-title">
      <div className="neu-inset grid h-28 w-28 place-items-center rounded-full">
        <span className="font-mono text-3xl font-black text-accent" aria-hidden="true">
          404
        </span>
      </div>
      <h1 id="nf-title" className="text-2xl font-black text-ink">
        Page not found
      </h1>
      <p className="text-ink">
        We couldn&apos;t find that page. Check the case ID (HHG-001 to HHG-020) or go back to the inbox.
      </p>
      <div className="flex flex-wrap justify-center gap-4">
        <Link href="/" className="neu-button focus-ring text-accent">
          Go to case inbox
        </Link>
        <Link href="/cases/HHG-001" className="neu-button focus-ring">
          Open HHG-001
        </Link>
      </div>
    </section>
  );
}
