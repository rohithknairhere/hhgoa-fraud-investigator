"use client";

import { useState } from "react";

import { ACTION_META, ROUTE_LABEL } from "@/lib/actions";
import type { RecommendedAction } from "@/lib/types";

type State = "pending" | "executed" | "awaiting";

// Only auto-route actions can be carried out directly. L1 and L2 actions go to a person for
// sign-off, as the fraud policy requires. Nothing here touches a real system.
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
                  {ROUTE_LABEL[a.route]} | {a.reason}
                </p>
              </div>
              <span
                className={`neu-inset rounded-full px-3 py-1 text-xs font-bold ${
                  s === "executed" ? "text-success" : s === "awaiting" ? "text-warning" : "text-ink-muted"
                }`}
              >
                {s === "executed" ? "Done" : s === "awaiting" ? `Waiting on ${a.route}` : a.route}
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
        {ran ? "Sent" : "Execute next best action"}
      </button>
      <p className="text-xs text-ink-muted" aria-live="polite">
        {ran
          ? `${autoCount} carried out, ${actions.length - autoCount} sent for approval.`
          : "Auto actions run straight away. L1 goes to a team lead and L2 to a fraud manager."}
      </p>
    </div>
  );
}
