"use client";

import { useState } from "react";

import type { ActionCode, ExecutionReceipt } from "@/lib/types";

import { ActionBadge } from "./ui";

type Status = { kind: "idle" } | { kind: "running" } | { kind: "done"; receipt: ExecutionReceipt } | { kind: "error"; message: string };

export function ActionTerminal({
  caseId,
  action,
  rationale,
  sarRequired,
}: {
  caseId: string;
  action: ActionCode;
  rationale: string;
  sarRequired: boolean;
}) {
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function execute() {
    setStatus({ kind: "running" });
    try {
      const res = await fetch(`/api/cases/${caseId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || body.error || `Request failed (${res.status})`);
      setStatus({ kind: "done", receipt: body as ExecutionReceipt });
      (window as unknown as { hhgoaAnalytics?: { track?: (n: string, p?: object) => void } }).hhgoaAnalytics?.track?.(
        "nba_executed",
        { caseId, action },
      );
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof Error ? err.message : "Execution failed" });
    }
  }

  const done = status.kind === "done";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="eyebrow">Recommended</span>
        <ActionBadge action={action} size="md" />
        {sarRequired && <span className="text-sm font-bold text-danger">SAR will be filed</span>}
      </div>
      <p className="text-sm text-ink">{rationale}</p>
      <button
        type="button"
        onClick={execute}
        disabled={status.kind === "running" || done}
        aria-pressed={done}
        className={`focus-ring w-full rounded-3xl bg-surface px-6 py-5 text-lg font-extrabold tracking-tight text-accent transition-shadow duration-150 sm:w-auto ${
          done ? "shadow-neu-inset" : "shadow-neu-lg hover:shadow-neu active:shadow-neu-inset"
        }`}
      >
        {status.kind === "running" ? "Executing..." : done ? "Next best action executed" : "Execute Next Best Action"}
      </button>
      <div aria-live="polite">
        {status.kind === "done" && (
          <dl className="neu-inset grid gap-2 rounded-2xl p-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="eyebrow">Execution id</dt>
              <dd className="font-mono text-ink">{status.receipt.execution_id}</dd>
            </div>
            <div>
              <dt className="eyebrow">Status</dt>
              <dd className="text-ink">
                {status.receipt.status}
                {status.receipt.idempotent_replay ? " (already executed)" : ""}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Action</dt>
              <dd className="text-ink">{status.receipt.label}</dd>
            </div>
            <div>
              <dt className="eyebrow">Executed at</dt>
              <dd className="font-mono text-ink">{status.receipt.executed_at}</dd>
            </div>
          </dl>
        )}
        {status.kind === "error" && (
          <p role="alert" className="neu-inset rounded-2xl p-4 text-sm font-semibold text-danger">
            {status.message}
          </p>
        )}
      </div>
    </div>
  );
}
