import "server-only";

import { promises as fs } from "fs";
import path from "path";

import { CASE_ID_PATTERN } from "@/lib/actions";
import type { CaseSummary, InvestigationRecord } from "@/lib/types";

// Server-only configuration. No NEXT_PUBLIC_ prefix, so the backend URL never reaches the browser bundle.
const BACKEND = process.env.BACKEND_API_URL?.replace(/\/$/, "");
const DATA_DIR = path.join(process.cwd(), "data", "benchmarks");

export async function backendFetch(pathname: string, init?: RequestInit & { revalidate?: number }) {
  if (!BACKEND) return null;
  const isRead = !init?.method || init.method === "GET";
  try {
    return await fetch(`${BACKEND}${pathname}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      signal: AbortSignal.timeout(2500),
      ...(isRead ? { next: { revalidate: init?.revalidate ?? 30 } } : { cache: "no-store" as const }),
    });
  } catch {
    return null;
  }
}

async function readLocal(caseId: string): Promise<InvestigationRecord | null> {
  if (!CASE_ID_PATTERN.test(caseId)) return null;
  try {
    return JSON.parse(await fs.readFile(path.join(DATA_DIR, `${caseId}.json`), "utf-8"));
  } catch {
    return null;
  }
}

function summarise(r: InvestigationRecord): CaseSummary {
  return {
    case_id: r.case_id,
    title: r.title,
    typology: r.typology,
    alert_rule: r.alert.rule,
    risk_score: r.alert.risk_score,
    transaction_id: r.alert.transaction_id,
    status: "investigated",
    initial_action: r.nba_before_additional_evidence.action,
    final_action: r.nba_after_additional_evidence.action,
    p_fraud: r.final_decision.p_fraud,
    confidence: r.final_decision.confidence,
    sar_required: r.sar.required,
  };
}

export async function listCaseIds(): Promise<string[]> {
  try {
    const files = await fs.readdir(DATA_DIR);
    return files
      .filter((f) => /^HHGOA-\d{3}\.json$/.test(f))
      .map((f) => f.replace(".json", ""))
      .sort();
  } catch {
    return [];
  }
}

export async function getCaseSummaries(): Promise<{ cases: CaseSummary[]; source: "live" | "snapshot" }> {
  const res = await backendFetch("/api/cases");
  if (res?.ok) {
    const body = (await res.json()) as { cases: CaseSummary[] };
    return { cases: body.cases, source: "live" };
  }
  const ids = await listCaseIds();
  const records = (await Promise.all(ids.map(readLocal))).filter(Boolean) as InvestigationRecord[];
  return { cases: records.map(summarise), source: "snapshot" };
}

export async function getCase(
  caseId: string,
): Promise<{ record: InvestigationRecord; source: "live" | "snapshot" } | null> {
  if (!CASE_ID_PATTERN.test(caseId)) return null;
  const res = await backendFetch(`/api/cases/${caseId}`, { revalidate: 30 });
  if (res?.ok) return { record: (await res.json()) as InvestigationRecord, source: "live" };
  const local = await readLocal(caseId);
  return local ? { record: local, source: "snapshot" } : null;
}
