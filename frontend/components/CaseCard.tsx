import Link from "next/link";

import { humanise, pct } from "@/lib/actions";
import type { CaseSummary } from "@/lib/types";

import { ActionBadge } from "./ui";

export function CaseCard({ c }: { c: CaseSummary }) {
  const changed = c.initial_action && c.final_action && c.initial_action !== c.final_action;
  return (
    <li>
      <Link
        href={`/cases/${c.case_id}`}
        className="focus-ring neu group flex h-full flex-col gap-4 p-5 transition-shadow hover:shadow-neu-lg"
        aria-label={`Open case ${c.case_id}: ${c.title}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-xs font-semibold text-ink-muted">{c.case_id}</p>
            <h3 className="mt-1 text-base font-bold leading-snug text-ink">{c.title}</h3>
          </div>
          <span
            className="neu-inset shrink-0 rounded-xl px-2.5 py-1 font-mono text-xs font-bold text-ink"
            title="Alert risk score"
          >
            {c.risk_score.toFixed(2)}
          </span>
        </div>
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          {humanise(c.typology)} | {c.alert_rule}
        </p>
        <div className="mt-auto space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span className="font-semibold">Initial NBA</span>
            <ActionBadge action={c.initial_action} />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span className="font-semibold">{changed ? "Updated NBA" : "Final NBA"}</span>
            <ActionBadge action={c.final_action} />
          </div>
          <p className="pt-1 text-xs text-ink-muted">
            p(fraud) <span className="font-mono font-bold text-ink">{pct(c.p_fraud)}</span>, confidence{" "}
            <span className="font-mono font-bold text-ink">{c.confidence?.toFixed(2) ?? "n/a"}</span>
            {c.sar_required && <span className="ml-2 font-bold text-danger">SAR</span>}
          </p>
        </div>
      </Link>
    </li>
  );
}
