"""Uncertainty assessment, next-best-action policy and SAR narrative."""

from __future__ import annotations

import math
from typing import Any

from app.agent.signals import ANALYST, IDENTITY, RELATIONSHIP

GRAPH_CATEGORIES = ("transaction_context", "customer_history", "related_entities", "similar_cases")
VERIFICATION_WEIGHT = 3.0
SAR_TAGS = {"device_sharing", "ip_cluster", "structuring", "synthetic_identity"}
SAR_AMOUNT_THRESHOLD = 5_000.0

ACTIONS: dict[str, dict[str, Any]] = {
    "ALLOW_TRANSACTION": {"label": "Allow transaction", "terminal": True},
    "BLOCK_TRANSACTION": {"label": "Block transaction & reissue card", "terminal": True},
    "BLOCK_AND_FILE_SAR": {"label": "Block, freeze account & file SAR", "terminal": True},
    "ESCALATE_TO_SENIOR_ANALYST": {"label": "Escalate to senior analyst", "terminal": True},
    "MONITOR_ACCOUNT_AND_REQUEST_STEP_UP_AUTH": {
        "label": "Monitor account + request step-up auth", "terminal": False, "request": "step_up_auth"},
    "HOLD_AND_REQUEST_ANALYST_REVIEW": {
        "label": "Hold funds + request analyst review", "terminal": False, "request": "analyst_review"},
}
REQUEST_FOR_CATEGORY = {IDENTITY: "step_up_auth", RELATIONSHIP: "analyst_review", ANALYST: "analyst_review"}
ACTION_FOR_REQUEST = {"step_up_auth": "MONITOR_ACCOUNT_AND_REQUEST_STEP_UP_AUTH",
                      "analyst_review": "HOLD_AND_REQUEST_ANALYST_REVIEW"}


def _logit(p: float) -> float:
    p = min(max(p, 0.01), 0.99)
    return math.log(p / (1 - p))


def assess(risk_score: float, signals: list[dict[str, Any]], graph_categories: set[str],
           verified_categories: set[str]) -> dict[str, Any]:
    prior = _logit(risk_score)
    contribs = [s["contribution"] for s in signals]
    total = prior + sum(contribs)
    p = 1 / (1 + math.exp(-total))
    decisiveness = abs(2 * p - 1)

    required = {s["needs_verification"] for s in signals if s.get("needs_verification")}
    req_weight = len(GRAPH_CATEGORIES) + VERIFICATION_WEIGHT * len(required)
    got_weight = len(graph_categories & set(GRAPH_CATEGORIES)) + VERIFICATION_WEIGHT * len(required & verified_categories)
    coverage = got_weight / req_weight

    pos = sum(c for c in contribs if c > 0)
    neg = -sum(c for c in contribs if c < 0)
    conflict = min(pos, neg) / max(pos, neg) if max(pos, neg) > 0 else 0.0

    confidence = max(0.0, min(1.0, decisiveness * (0.4 + 0.6 * coverage) - 0.15 * conflict))
    return {
        "p_fraud": round(p, 4),
        "confidence": round(confidence, 4),
        "components": {
            "prior_log_odds": round(prior, 3),
            "signal_log_odds": round(sum(contribs), 3),
            "decisiveness": round(decisiveness, 4),
            "evidence_coverage": round(coverage, 4),
            "signal_conflict": round(conflict, 4),
        },
        "required_verifications": sorted(required),
        "missing_verifications": sorted(required - verified_categories),
    }


def choose_action(assessment: dict[str, Any], signals: list[dict[str, Any]], pattern_tags: list[str],
                  aggregate_amount: float, threshold: float, rounds_used: int, max_rounds: int,
                  requests_made: list[str]) -> dict[str, Any]:
    p, conf = assessment["p_fraud"], assessment["confidence"]
    top = sorted(signals, key=lambda s: -abs(s["contribution"]))[:4]
    drivers = [s["name"] for s in top]

    if conf >= threshold:
        if p >= 0.5:
            sar = p >= 0.85 and (bool(SAR_TAGS & set(pattern_tags)) or aggregate_amount >= SAR_AMOUNT_THRESHOLD)
            action = "BLOCK_AND_FILE_SAR" if sar else "BLOCK_TRANSACTION"
            why = f"Fraud probability {p:.0%} with confidence {conf:.2f}, at or above the {threshold:.2f} threshold."
        else:
            action = "ALLOW_TRANSACTION"
            why = f"Fraud probability {p:.0%} with confidence {conf:.2f}, at or above the {threshold:.2f} threshold."
        return _nba(action, why, drivers, None)

    request = None
    for cat in assessment["missing_verifications"]:
        candidate = REQUEST_FOR_CATEGORY[cat]
        if candidate not in requests_made:
            request = candidate
            break
    if request is None:
        request = next((r for r in ("step_up_auth", "analyst_review") if r not in requests_made), None)

    if rounds_used >= max_rounds or request is None:
        why = (f"Confidence {conf:.2f} remains below {threshold:.2f} after {rounds_used} evidence round(s); "
               "automated resolution is not justified.")
        return _nba("ESCALATE_TO_SENIOR_ANALYST", why, drivers, None)

    missing = ", ".join(assessment["missing_verifications"]) or "corroborating evidence"
    why = f"Confidence {conf:.2f} is below the {threshold:.2f} threshold (p_fraud {p:.0%}). Missing: {missing}."
    return _nba(ACTION_FOR_REQUEST[request], why, drivers, request)


def _nba(action: str, rationale: str, drivers: list[str], request: str | None) -> dict[str, Any]:
    meta = ACTIONS[action]
    return {"action": action, "label": meta["label"], "terminal": meta["terminal"],
            "rationale": rationale, "key_drivers": drivers, "evidence_request": request}


def sar_narrative(case_id: str, alert: dict[str, Any], ctx: dict[str, Any], assessment: dict[str, Any],
                  signals: list[dict[str, Any]], pattern_tags: list[str]) -> dict[str, Any]:
    txn, cust, card, dev, ip = ctx["transaction"], ctx["customer"], ctx["card"], ctx["device"], ctx["ip"]
    stats = ctx["stats"]
    fraud_signals = [s for s in signals if s["contribution"] > 0]
    fraud_signals.sort(key=lambda s: -s["contribution"])
    aggregate = max(stats["customer_amount_24h"], txn["amount"])
    lines = [
        f"Subject: customer {cust['id']} (tenure {cust['tenure_days']} days, KYC level {cust['kyc_level']}), "
        f"card {card['id']} ({card['card4']} {card['card6']}).",
        f"Activity: transaction {txn['id']} for ${txn['amount']:,.2f} (product {txn['product_cd']}) at "
        f"TransactionDT {txn['ts']}, via device {dev['id']} ({dev['device_info']}) and IP {ip['id']} "
        f"({ip['country']}, {ip['asn']}{', proxy' if ip.get('is_proxy') else ''}). "
        f"Related 24h activity totals ${aggregate:,.2f}.",
        f"Typology: {', '.join(pattern_tags) or 'unclassified'}. Alert {alert['rule']} fired with risk score "
        f"{alert['risk_score']:.2f}; graph investigation raised fraud probability to {assessment['p_fraud']:.0%} "
        f"(confidence {assessment['confidence']:.2f}).",
        "Basis for suspicion (from TigerGraph evidence):",
        *[f"  - {s['description']} [evidence {', '.join(s['evidence_ids'])}]" for s in fraud_signals[:6]],
        "Action taken: transaction blocked, account frozen pending review, related cards flagged for reissue.",
    ]
    return {
        "required": True,
        "filing_type": "FinCEN SAR (simulated)",
        "subject_ids": sorted({cust["id"], card["id"], dev["id"], ip["id"]}),
        "suspicious_amount": round(aggregate, 2),
        "narrative": "\n".join(lines),
    }
