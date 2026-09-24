import { ACTION_META, ROUTE_LABEL, type Tone } from "@/lib/actions";
import type { RecommendedAction } from "@/lib/types";

export const TONE_TEXT: Record<Tone, string> = {
  danger: "text-danger",
  warning: "text-warning",
  success: "text-success",
  accent: "text-accent",
};
export const TONE_DOT: Record<Tone, string> = {
  danger: "bg-danger",
  warning: "bg-warning",
  success: "bg-success",
  accent: "bg-accent",
};

export function Pill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={`neu-inset inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${TONE_TEXT[tone]}`}>
      <span aria-hidden="true" className={`h-2 w-2 rounded-full ${TONE_DOT[tone]}`} />
      {children}
    </span>
  );
}

export function ActionChip({ a, showReason = false }: { a: RecommendedAction; showReason?: boolean }) {
  const meta = ACTION_META[a.action] ?? { label: a.action, tone: "accent" as Tone };
  return (
    <li className="neu-sm flex flex-col gap-1 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={`text-sm font-bold ${TONE_TEXT[meta.tone]}`}>{meta.label}</span>
        <span className="neu-inset rounded-full px-2.5 py-0.5 font-mono text-xs font-bold text-ink" title={ROUTE_LABEL[a.route]}>
          {a.route}
        </span>
      </div>
      {showReason && <p className="text-xs text-ink">{a.reason}</p>}
    </li>
  );
}

export function Meter({ label, value, tone = "accent" }: { label: string; value: number; tone?: Tone }) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs font-semibold">
        <span className="text-ink-muted">{label}</span>
        <span className="font-mono text-ink">{pct.toFixed(2)}</span>
      </div>
      <div
        className="neu-inset h-3 overflow-hidden rounded-full p-0.5"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={Number(pct.toFixed(2))}
      >
        <div className={`h-full rounded-full ${TONE_DOT[tone]}`} style={{ width: `${pct * 100}%` }} />
      </div>
    </div>
  );
}

export function Section({
  id,
  title,
  eyebrow,
  children,
  className = "",
}: {
  id?: string;
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined} className={`neu p-5 sm:p-6 ${className}`}>
      {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
      <h2 id={id ? `${id}-title` : undefined} className="mb-4 text-lg font-bold text-ink sm:text-xl">
        {title}
      </h2>
      {children}
    </section>
  );
}
