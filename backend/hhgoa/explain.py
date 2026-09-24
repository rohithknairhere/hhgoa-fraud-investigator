"""GraphRAG explanation step.

The decision itself is made by the policy engine. This step retrieves the policy rules, pattern
descriptions and closed-case narratives most relevant to the case from TigerGraph vector search,
passes them to Gemini together with the graph evidence, and asks for the case summary, the SAR
narrative and (for undocumented patterns) a pattern description. Output is validated: any ID the
model mentions must exist in the evidence it was given, otherwise the template text is kept.
"""

from __future__ import annotations

import json
import re
from typing import Any

SYSTEM = """You are a senior card-fraud investigator at a bank writing the record for a case your
investigation agent has already decided. Write in plain, direct English as a human analyst would.
Do not use em dashes, en dashes, arrows, bullet symbols or markdown. Use only the facts, IDs, dates
and amounts given to you; never invent an ID, merchant, name or number. Cite policy rules by number
(R1 to R10, 3a, 6) where they justify the actions. Return JSON only."""

ID_RE = re.compile(r"\b(?:\d{7}|C\d{5}-K\d|C\d{5}|CC-\d{4}|HHG-\d{3}|INV-HHG-\d{3}|KC-\d{4})\b")


def _clean(text: str) -> str:
    text = text.replace("—", ", ").replace("–", "-").replace("→", "to").replace("  ", " ")
    return re.sub(r"\s+,", ",", text).strip()


def build_prompt(case: dict, answer: dict, knowledge: list[dict], closed: list[dict], sar_template: str) -> str:
    c = answer["case"]
    nba = answer["next_best_actions"]
    lines = [
        f"CASE {case['case_id']}, opened {case['opened_at']}, trigger {case['trigger_type']}: {case['trigger_text']}",
        f"Flagged transaction {case['flagged_txn_id']} on card {case['card_id']} (customer {case['customer_id']}).",
        f"Decision: verdict {c['verdict']}, status {c['status']}, fraud probability {c['fraud_probability']}, "
        f"pattern {c['pattern']}, exposure ${c['exposure_usd']:,.2f}.",
        f"Affected transactions: {', '.join(c['affected_txn_ids']) or 'none'}. Connected cards: {', '.join(c['connected_card_ids'][:10]) or 'none'}.",
        f"Device profiles: {', '.join(c['connected_device_profiles']) or 'none'}.",
        "GRAPH EVIDENCE:",
        *[f"- [{e['source']}] {e['claim']}" for e in c["evidence"]],
        "EVIDENCE REQUESTS: " + ("; ".join(f"{r['type']}: {r['assumed_response']}" for r in answer["evidence_requests"]) or "none"),
        "INITIAL ACTIONS: " + "; ".join(f"{a['action']} ({a['route']}): {a['reason']}" for a in nba["initial"]),
        "FINAL ACTIONS: " + "; ".join(f"{a['action']} ({a['route']}): {a['reason']}" for a in nba["final"]),
        f"FILE_REPORT recommended: {answer['sar']['file']}",
        "RETRIEVED POLICY AND PATTERN TEXT (TigerGraph vector search):",
        *[f"- {k['chunk_id']} [{k['section']}]: {k['text'][:700]}" for k in knowledge],
        "RETRIEVED CLOSED CASES:",
        *[f"- {x['case_id']} ({x['outcome']}, {x['pattern']}): {str(x.get('analyst_notes', ''))[:400]}" for x in closed],
    ]
    if answer["sar"]["file"]:
        lines.append("FACT SHEET FOR THE REPORT (use these facts): " + sar_template)
    lines.append("""
Return JSON with these keys:
"summary": two to six sentences an analyst could read, saying what happened, what the evidence shows, what was assumed, and what is recommended.
"pattern_description": if the pattern is undocumented, two or three sentences on what the pattern is, who it affects and how it was found; otherwise "".
"sar_narrative": if FILE_REPORT is recommended, a standalone suspicious activity report of six to twelve sentences covering who, what, when, where, how and why it is suspicious; otherwise "".
"document_evidence": up to three objects {"claim": one sentence stating which retrieved policy rule or documented pattern applies to this case and why, "chunk_id": the KC id of that policy or pattern text}. Prefer policy rules and pattern descriptions over closed cases.
"policy_consistent": true or false, whether the final actions follow the retrieved policy text.
""")
    return "\n".join(lines)


def allowed_ids(case: dict, answer: dict, knowledge: list[dict], closed: list[dict]) -> set[str]:
    blob = json.dumps(answer) + json.dumps(case, default=str) + json.dumps(knowledge) + json.dumps(closed, default=str)
    return set(ID_RE.findall(blob))


def explain(llm, source, case: dict, answer: dict, sar_template: str) -> dict[str, Any]:
    c = answer["case"]
    query = (f"{case['trigger_type']} {c['pattern']} {c['verdict']}. " +
             " ".join(e["claim"] for e in c["evidence"][:6]))[:2000]
    qv = llm.embed([query], task="RETRIEVAL_QUERY")[0]
    knowledge = source.search_knowledge(qv, k=5, sources=["policy", "patterns"]) + \
        source.search_knowledge(qv, k=3, sources=["closed_case"])
    closed = source.closed_info(c["similar_prior_cases"][:4])
    prompt = build_prompt(case, answer, knowledge, closed, sar_template)
    out = llm.generate_json(SYSTEM, prompt)
    ok_ids = allowed_ids(case, answer, knowledge, closed)
    result: dict[str, Any] = {"model": llm.last_model, "knowledge": knowledge, "policy_consistent": out.get("policy_consistent")}
    for key in ("summary", "pattern_description", "sar_narrative"):
        text = _clean(str(out.get(key) or ""))
        bad = set(ID_RE.findall(text)) - ok_ids
        result[key] = text if text and not bad else ""
        if bad:
            result[f"{key}_rejected_ids"] = sorted(bad)
    chunk_ids = {k["chunk_id"]: k for k in knowledge}
    docs = []
    for d in out.get("document_evidence") or []:
        cid = str(d.get("chunk_id", ""))
        if cid in chunk_ids and d.get("claim"):
            docs.append({"claim": _clean(str(d["claim"])), "source": "document",
                         "ref": f"{cid} ({chunk_ids[cid]['section']})", "entity_ids": []})
    result["document_evidence"] = docs[:3]
    return result
