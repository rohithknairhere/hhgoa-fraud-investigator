import Link from "next/link";

import { ACTION_META, VERDICT_TONE, humanise, money } from "@/lib/actions";
import type { CaseView } from "@/lib/types";

import { Pill } from "./ui";

const TRIGGER_LABEL = { risk_score: "Risk score", customer_report: "Customer report", analyst_request: "Analyst request" };

export function CaseCard({ view }: { view: CaseView }) {
  const { pack, answer } = view;
  const c = answer.case;
  // Show the first decisive action on each side (opening the case is common to most of them).
  const decisive = (list: typeof answer.next_best_actions.initial) => list.find((a) => a.action !== "CREATE_CASE") ?? list[0];
  const first = decisive(answer.next_best_actions.initial);
  const last = decisive(answer.next_best_actions.final);
  const changed = answer.next_best_actions.what_changed !== "nothing" && first?.action !== last?.action;
  return (
    <li>
      <Link
        href={`/cases/${pack.case_id}`}
        className="focus-ring neu group flex h-full flex-col gap-3 p-5 transition-shadow hover:shadow-neu-lg"
        aria-label={`Open case ${pack.case_id}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-xs font-semibold text-ink-muted">{pack.case_id}</p>
            <h3 className="mt-1 text-base font-bold leading-snug text-ink">
              {TRIGGER_LABEL[pack.trigger_type]} on {pack.card_id}
            </h3>
          </div>
          <Pill tone={VERDICT_TONE[c.verdict]}>{c.verdict}</Pill>
        </div>
        <p className="line-clamp-2 text-sm text-ink">{pack.trigger_text}</p>
        <dl className="grid grid-cols-3 gap-2 text-xs">
          <div className="neu-inset rounded-xl p-2">
            <dt className="text-ink-muted">p(fraud)</dt>
            <dd className="font-mono font-bold text-ink">{c.fraud_probability.toFixed(2)}</dd>
          </div>
          <div className="neu-inset rounded-xl p-2">
            <dt className="text-ink-muted">Exposure</dt>
            <dd className="font-mono font-bold text-ink">{money(c.exposure_usd)}</dd>
          </div>
          <div className="neu-inset rounded-xl p-2">
            <dt className="text-ink-muted">Pattern</dt>
            <dd className="truncate font-bold text-ink" title={humanise(c.pattern)}>
              {humanise(c.pattern)}
            </dd>
          </div>
        </dl>
        <p className="mt-auto text-xs text-ink">
          <span className="font-semibold text-ink-muted">Next best action: </span>
          {first ? ACTION_META[first.action]?.label : "none"}
          {changed && last ? <>, then <strong>{ACTION_META[last.action]?.label}</strong></> : null}
          {answer.sar.file && <span className="ml-2 font-bold text-danger">SAR</span>}
          {c.written_to_graph && <span className="ml-2 font-semibold text-success">In TigerGraph</span>}
        </p>
      </Link>
    </li>
  );
}
