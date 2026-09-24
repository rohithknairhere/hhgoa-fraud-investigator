import "server-only";

import { promises as fs } from "fs";
import path from "path";

import { CASE_ID_PATTERN } from "@/lib/actions";
import type { Answer, CasePackEntry, CaseView } from "@/lib/types";

import casePack from "@/data/case_pack.json";

const DATA_DIR = path.join(process.cwd(), "data", "cases");
const PACK = casePack as CasePackEntry[];

export async function listCaseIds(): Promise<string[]> {
  try {
    const files = await fs.readdir(DATA_DIR);
    return files
      .filter((f) => /^HHG-\d{3}\.json$/.test(f))
      .map((f) => f.replace(".json", ""))
      .sort();
  } catch {
    return [];
  }
}

export async function getCase(caseId: string): Promise<CaseView | null> {
  if (!CASE_ID_PATTERN.test(caseId)) return null;
  const pack = PACK.find((p) => p.case_id === caseId);
  if (!pack) return null;
  try {
    const answer = JSON.parse(await fs.readFile(path.join(DATA_DIR, `${caseId}.json`), "utf-8")) as Answer;
    return { pack, answer };
  } catch {
    return null;
  }
}

export async function getAllCases(): Promise<CaseView[]> {
  const ids = await listCaseIds();
  const views = await Promise.all(ids.map(getCase));
  return views.filter(Boolean) as CaseView[];
}
