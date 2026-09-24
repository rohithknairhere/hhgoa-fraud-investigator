import type { PolicyAction, Route } from "./types";

export type Tone = "danger" | "warning" | "success" | "accent";

export const ACTION_META: Record<PolicyAction, { label: string; tone: Tone }> = {
  ALLOW_TRANSACTION: { label: "Allow transaction", tone: "success" },
  DECLINE_TRANSACTION: { label: "Decline transaction", tone: "danger" },
  MONITOR_CARD: { label: "Monitor card", tone: "accent" },
  MONITOR_CONNECTED_CARDS: { label: "Monitor connected cards", tone: "accent" },
  WARN_CUSTOMER: { label: "Warn customer", tone: "accent" },
  VERIFY_WITH_CUSTOMER: { label: "Verify with customer", tone: "accent" },
  STEP_UP_AUTH: { label: "Step-up authentication", tone: "accent" },
  BLOCK_CARD: { label: "Block card", tone: "danger" },
  BLOCK_ALL_CARDS: { label: "Block all cards", tone: "danger" },
  GENERATE_REPORT: { label: "Generate internal report", tone: "accent" },
  CREATE_CASE: { label: "Create case", tone: "accent" },
  FILE_REPORT: { label: "File SAR", tone: "danger" },
  ESCALATE_TO_ANALYST: { label: "Escalate to analyst", tone: "warning" },
  CLOSE_NO_FRAUD: { label: "Close, no fraud", tone: "success" },
};

export const ROUTE_LABEL: Record<Route, string> = {
  auto: "Agent may act",
  L1: "Team lead approval",
  L2: "Fraud manager approval",
};

export const VERDICT_TONE: Record<string, Tone> = { fraud: "danger", legitimate: "success", uncertain: "warning" };

export const CASE_ID_PATTERN = /^HHG-\d{3}$/;

export function pct(x: number | undefined): string {
  return x === undefined ? "n/a" : `${Math.round(x * 100)}%`;
}

export function humanise(s: string): string {
  return s.replace(/_/g, " ");
}

export function money(x: number): string {
  return `$${x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
