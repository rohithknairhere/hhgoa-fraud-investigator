import Link from "next/link";

export function LegalPage({
  title,
  updated,
  sections,
}: {
  title: string;
  updated: string;
  sections: { heading: string; body: React.ReactNode }[];
}) {
  return (
    <article className="neu mx-auto max-w-3xl space-y-6 p-6 sm:p-10">
      <header className="space-y-2">
        <p className="eyebrow">Legal</p>
        <h1 className="text-3xl font-black tracking-tight text-ink">{title}</h1>
        <p className="text-sm text-ink-muted">Last updated {updated}</p>
      </header>
      {sections.map((s) => (
        <section key={s.heading} className="space-y-2">
          <h2 className="text-lg font-bold text-ink">{s.heading}</h2>
          <div className="space-y-2 text-base leading-7 text-ink">{s.body}</div>
        </section>
      ))}
      <p className="pt-4 text-sm">
        <Link href="/" className="focus-ring rounded font-semibold text-accent underline underline-offset-4">
          Back to cases
        </Link>
      </p>
    </article>
  );
}
