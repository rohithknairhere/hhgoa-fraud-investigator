import type { ActionCode } from "./types";

export type Tone = "danger" | "warning" | "success" | "accent";

export const ACTION_META: Record<ActionCode, { label: string; tone: Tone }> = {
  ALLOW_TRANSACTION: { label: "Allow transaction", tone: "success" },
  BLOCK_TRANSACTION: { label: "Block transaction", tone: "danger" },
  BLOCK_AND_FILE_SAR: { label: "Block + file SAR", tone: "danger" },
  ESCALATE_TO_SENIOR_ANALYST: { label: "Escalate to senior analyst", tone: "warning" },
  MONITOR_ACCOUNT_AND_REQUEST_STEP_UP_AUTH: { label: "Monitor + step-up auth", tone: "accent" },
  HOLD_AND_REQUEST_ANALYST_REVIEW: { label: "Hold + analyst review", tone: "accent" },
};

export const CASE_ID_PATTERN = /^HHGOA-\d{3}$/;

export function pct(x: number | undefined): string {
  return x === undefined ? "n/a" : `${Math.round(x * 100)}%`;
}

export function humanise(s: string): string {
  return s.replace(/_/g, " ");
}
