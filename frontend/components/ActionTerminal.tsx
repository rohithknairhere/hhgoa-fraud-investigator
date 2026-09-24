"use client";

import { useState } from "react";

import { ACTION_META, ROUTE_LABEL } from "@/lib/actions";
import type { RecommendedAction } from "@/lib/types";

type State = "pending" | "executed" | "awaiting";

// The agent may only execute auto-route actions itself. L1 and L2 actions are sent for human
// approval, as the fraud policy requires. Execution here is simulated.
export function ActionTerminal({ actions }: { actions: RecommendedAction[] }) {
  const [state, setState] = useState<Record<number, State>>({});
  const [ran, setRan] = useState(false);

  function execute() {
    const next: Record<number, State> = {};
    actions.forEach((a, i) => {
      next[i] = a.route === "auto" ? "executed" : "awaiting";
    });
    setState(next);
    setRan(true);
    (window as unknown as { hhgoaAnalytics?: { track?: (n: string) => void } }).hhgoaAnalytics?.track?.("nba_executed");
  }

  const autoCount = actions.filter((a) => a.route === "auto").length;
  return (
    <div className="space-y-4">
      <ol className="space-y-2">
        {actions.map((a, i) => {
          const s = state[i] ?? "pending";
          return (
            <li key={`${a.action}-${i}`} className="neu-sm flex flex-wrap items-center justify-between gap-2 p-3">
              <div>
                <p className="text-sm font-bold text-ink">
                  {i + 1}. {ACTION_META[a.action]?.label ?? a.action}
                </p>
                <p className="text-xs text-ink-muted">
                  {a.route} ({ROUTE_LABEL[a.route]}) | {a.reason}
                </p>
              </div>
              <span
                className={`neu-inset rounded-full px-3 py-1 text-xs font-bold ${
                  s === "executed" ? "text-success" : s === "awaiting" ? "text-warning" : "text-ink-muted"
                }`}
              >
                {s === "executed" ? "Executed" : s === "awaiting" ? `Sent for ${a.route} approval` : "Pending"}
              </span>
            </li>
          );
        })}
      </ol>
      <button
        type="button"
        onClick={execute}
        disabled={ran}
        aria-pressed={ran}
        className={`focus-ring w-full rounded-3xl bg-surface px-6 py-5 text-lg font-extrabold tracking-tight text-accent transition-shadow duration-150 sm:w-auto ${
          ran ? "shadow-neu-inset" : "shadow-neu-lg hover:shadow-neu active:shadow-neu-inset"
        }`}
      >
        {ran ? "Next best action executed" : "Execute Next Best Action"}
      </button>
      <p className="text-xs text-ink-muted" aria-live="polite">
        {ran
          ? `${autoCount} action(s) executed by the agent; ${actions.length - autoCount} sent to a human approver.`
          : "Only auto-route actions run automatically. L1 and L2 actions wait for a human, per the approval policy."}
      </p>
    </div>
  );
}
