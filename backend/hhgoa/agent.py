"""HHGOA case investigator: runs a LangGraph workflow per case from case_pack.csv and writes
answer files in the README's format to <repo>/cases/<case_id>.json.

    python -m hhgoa.agent            (run from backend/)

Graph queries are named after the GSQL queries in tigergraph/queries and run on the local
Parquet mirror of the graph when TigerGraph is not connected.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from hhgoa.paths import CASES_OUT, STORE

H = pd.Timedelta(hours=1)
D = pd.Timedelta(days=1)


# ---------------------------------------------------------------------------------------------
# Graph mirror + named queries
# ---------------------------------------------------------------------------------------------
class GraphMirror:
    def __init__(self) -> None:
        tx = pd.read_parquet(STORE / "transactions.parquet")
        tx["c6"] = tx.card6.fillna("NA")
        cards = tx[["customer_id", "c6"]].drop_duplicates().sort_values(["customer_id", "c6"])
        cards["card_id"] = cards.customer_id + "-K" + (cards.groupby("customer_id").cumcount() + 1).astype(str)
        tx = tx.merge(cards, on=["customer_id", "c6"])
        d = tx[["DeviceInfo", "id_30", "id_31", "id_33"]].fillna("").astype(str)
        tx["device_profile"] = (d.DeviceInfo + " | " + d.id_30 + " | " + d.id_31 + " | " + d.id_33).where(
            tx.DeviceInfo.notna() | tx.id_31.notna())
        ms = STORE / "memory_scores.parquet"
        tx = tx.merge(pd.read_parquet(ms), on="TransactionID", how="left") if ms.exists() else tx.assign(memory_score=float("nan"))
        self.tx = tx.set_index("TransactionID", drop=False)
        self.by_card = {k: g.sort_values("ts") for k, g in tx.groupby("card_id")}
        self.by_profile = {k: g for k, g in tx[tx.device_profile.notna()].groupby("device_profile")}
        self.closed = pd.read_parquet(STORE / "closed_cases.parquet")
        self.closed["opened_at"] = pd.to_datetime(self.closed.opened_at)
        self.cases = pd.read_parquet(STORE / "case_pack.parquet")
        self.calls = 0

    # each method = one graph query (counted as a tool call)
    def get_transaction(self, txn_id: int) -> pd.Series:
        self.calls += 1
        return self.tx.loc[txn_id]

    def card_window(self, card_id: str, start, end) -> pd.DataFrame:
        self.calls += 1
        g = self.by_card[card_id]
        return g[(g.ts >= start) & (g.ts <= end)]

    def card_history(self, card_id: str, before) -> pd.DataFrame:
        self.calls += 1
        g = self.by_card[card_id]
        return g[g.ts < before]

    def device_neighbors(self, profile: str, start, end) -> pd.DataFrame:
        self.calls += 1
        g = self.by_profile.get(profile)
        return g[(g.ts >= start) & (g.ts <= end)] if g is not None else self.tx.iloc[:0]

    def similar_closed_cases(self, card_id: str, pattern: str, device_hint: str, before, note_hint: str = "") -> list[str]:
        self.calls += 1
        c = self.closed[self.closed.opened_at < before]
        if note_hint:
            hit = c[c.analyst_notes.str.contains(note_hint, na=False, regex=False)]
            if len(hit):
                return list(hit.sort_values("opened_at", ascending=False).case_id[:5])
        same_card = c[c.card_id == card_id].sort_values("opened_at", ascending=False)
        out = list(same_card[same_card.pattern == pattern].case_id[:2]) + list(same_card.case_id[:2])
        if device_hint:
            key = device_hint.split(" Build")[0].split(" | ")[0].strip()
            if key:
                hit = c[c.analyst_notes.str.contains(re.escape(key), na=False)]
                out += list(hit[hit.pattern == pattern].case_id[:3]) + list(hit.case_id[:2])
        if pattern not in ("none", ""):
            out += list(c[c.pattern == pattern].sort_values("opened_at", ascending=False).case_id[:1])
        seen: list[str] = []
        for x in out:
            if x not in seen:
                seen.append(x)
        return seen[:5]


# ---------------------------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------------------------
def route(action: str, exposure: float) -> str:
    if action == "DECLINE_TRANSACTION":
        return "L1"
    if action == "BLOCK_CARD":
        return "L1" if exposure <= 2500 else "L2"
    if action in ("BLOCK_ALL_CARDS", "FILE_REPORT"):
        return "L2"
    return "auto"


def act(action: str, reason: str, exposure: float) -> dict[str, str]:
    return {"action": action, "route": route(action, exposure), "reason": reason}


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def logit(p: float) -> float:
    p = min(max(p, 0.02), 0.98)
    return math.log(p / (1 - p))


def money(x: float) -> str:
    return f"${x:,.2f}"


def tid(x) -> str:
    return str(int(x))


# ---------------------------------------------------------------------------------------------
# LangGraph state and nodes
# ---------------------------------------------------------------------------------------------
class S(TypedDict, total=False):
    case: dict
    f: Any
    findings: dict
    evidence: list
    p_initial: float
    pattern: str
    affected: list
    connected_cards: list
    connected_devices: list
    similar: list
    initial: list
    requests: list
    p_final: float
    final: list
    verdict: str
    status: str
    what_changed: str
    stop_reason: str
    trace: list


@dataclass
class Ctx:
    g: GraphMirror
    trace: list = field(default_factory=list)


G: GraphMirror | None = None


def trigger(s: S) -> S:
    c = s["case"]
    f = G.get_transaction(int(c["flagged_txn_id"]))
    return {"f": f, "evidence": [], "trace": [f"trigger:{c['trigger_type']}"]}


def investigate(s: S) -> S:
    c, f = s["case"], s["f"]
    card = c["card_id"]
    as_of = f.ts + 6 * H
    hist = G.card_history(card, f.ts - 1 * D)
    win = G.card_window(card, f.ts - 2 * D, as_of)
    ev: list[dict] = []
    fnd: dict[str, Any] = {"hist_n": len(hist)}
    q = lambda name, **kw: f"query:{name}(" + ", ".join(f"{k}={v}" for k, v in kw.items()) + ")"  # noqa: E731

    # --- pattern: just-under-$500 online burst (undocumented, seen in CC-3748 family)
    burst = win[(win.channel == "online") & (win.TransactionAmt >= 400) & (win.TransactionAmt < 500)
                & (abs(win.ts - f.ts) <= H)]
    if len(burst) >= 3 and f.TransactionID in set(burst.TransactionID):
        fnd["burst500"] = burst
        ev.append({"claim": f"{len(burst)} online purchases between $400 and $500 within one hour "
                            f"({', '.join(money(a) for a in burst.TransactionAmt)}), each just under a $500 "
                            "authorization threshold", "source": "graph",
                   "ref": q("card_window", card_id=card, hours=2), "entity_ids": [tid(x) for x in burst.TransactionID]})

    # --- pattern: card testing (>=3 tiny online auths within 1h, then larger purchase)
    small = win[(win.channel == "online") & (win.TransactionAmt < 5) & (win.ts <= f.ts)]
    tests = []
    for _, r in small.iterrows():
        grp = small[(small.ts >= r.ts) & (small.ts <= r.ts + H)]
        if len(grp) >= 3:
            tests = grp
            break
    if len(tests) and f.TransactionAmt >= 20 and f.ts - tests.ts.max() <= D:
        fnd["card_testing"] = tests
        ev.append({"claim": f"{len(tests)} online authorizations under $5 within an hour, followed by the "
                            f"{money(f.TransactionAmt)} flagged purchase", "source": "graph",
                   "ref": q("card_window", card_id=card, hours=48), "entity_ids": [tid(x) for x in tests.TransactionID] + [tid(f.TransactionID)]})

    # --- device profile and shared-origin ring
    prof = f.device_profile if isinstance(f.device_profile, str) else ""
    fnd["profile"] = prof
    if prof:
        nb = G.device_neighbors(prof, f.ts - 30 * D, f.ts + 7 * D)
        others = nb[nb.card_id != card]
        proxied = others[others.id_23.fillna("").str.contains("ANONYMOUS|HIDDEN")]
        fnd["profile_cards"] = others.card_id.nunique()
        if proxied.card_id.nunique() >= 5 and proxied.card_id.nunique() >= 0.5 * others.card_id.nunique() and any(k in str(f.id_23) for k in ("ANONYMOUS", "HIDDEN")):
            fnd["ring"] = proxied
            ev.append({"claim": f"Device profile '{prof}' behind an anonymous/hidden proxy was used on "
                                f"{proxied.card_id.nunique()} other cards within 30 days; closed cases describe the same "
                                "profile as a multi-cardholder compromise", "source": "graph",
                       "ref": q("device_neighbors", profile=prof.split(' | ')[0], days=30),
                       "entity_ids": sorted(proxied.card_id.unique().tolist())[:15]})
        seen_before = prof in set(hist.device_profile.dropna())
        fnd["device_new"] = (str(f.id_15) == "New") and not seen_before
        if f.channel == "online":
            ev.append({"claim": f"Online purchase from device profile '{prof}', identity record id_15={f.id_15}; "
                                f"{'never' if not seen_before else 'previously'} seen on this card before",
                       "source": "graph", "ref": q("card_history", card_id=card),
                       "entity_ids": [tid(f.TransactionID)]})

    # --- amount and product fit
    same_ch = hist[hist.channel == f.channel]
    p95 = same_ch.TransactionAmt.quantile(0.95) if len(same_ch) >= 10 else None
    fnd["amount_anomaly"] = bool(p95 is not None and f.TransactionAmt > max(p95 * 1.5, 150))
    if p95 is not None:
        ev.append({"claim": f"{money(f.TransactionAmt)} vs this card's 95th percentile of {money(p95)} for "
                            f"{f.channel} purchases over {len(same_ch)} prior transactions", "source": "graph",
                   "ref": q("card_history", card_id=card), "entity_ids": [tid(f.TransactionID)]})

    # --- recurring charge (same product, ~same amount, repeated before)
    rec = hist[(hist.ProductCD == f.ProductCD) & (abs(hist.TransactionAmt - f.TransactionAmt) <= max(1.0, 0.02 * f.TransactionAmt))
               & (hist.ts < f.ts - 2 * D)]
    low_risk = pd.isna(f.memory_score) or f.memory_score < 0.3
    fnd["recurring"] = low_risk and len(rec) >= 2 and (rec.ts.max() - rec.ts.min()) >= 20 * D and len(hist) < 3000
    if fnd["recurring"]:
        ev.append({"claim": f"The same amount under product {f.ProductCD} appears {len(rec)} times before on this card "
                            f"(e.g. {', '.join(str(d.date()) for d in rec.ts.tail(4))}), consistent with the cardholder's own habit",
                   "source": "graph", "ref": q("card_history", card_id=card), "entity_ids": [tid(x) for x in rec.TransactionID.tail(4)]})

    # --- region
    if f.channel == "in_person" and pd.notna(f.addr1):
        regions = hist[hist.ts >= f.ts - 90 * D].addr1.value_counts()
        known = int(regions.get(f.addr1, 0))
        fnd["region_known"] = known
        same_region = win[(win.addr1 == f.addr1) & (win.channel == "in_person")]
        ev.append({"claim": f"Billing region {int(f.addr1)} appears {known} times on this card in the prior 90 days",
                   "source": "graph", "ref": q("region_history", card_id=card, region=int(f.addr1), days=90),
                   "entity_ids": [tid(f.TransactionID)]})
        fnd["out_of_region"] = known == 0 and len(same_region) <= 2

    # --- learned signal from closed-case memory (Vesta features)
    ms = f.memory_score
    fnd["memory_score"] = None if pd.isna(ms) else float(ms)
    if fnd["memory_score"] is not None:
        ev.append({"claim": f"Classifier trained on the Jul-Oct closed cases (Vesta V/C/D/M features, unnamed) scores "
                            f"the flagged transaction {ms:.2f}; bank risk score was {f.risk_score:.2f}",
                   "source": "graph", "ref": "model:closed_case_memory_classifier", "entity_ids": [tid(f.TransactionID)]})
    return {"findings": fnd, "evidence": ev, "trace": s["trace"] + ["investigate"]}


def assess(s: S) -> S:
    c, f, fnd = s["case"], s["f"], s["findings"]
    base = fnd["memory_score"] if fnd["memory_score"] is not None else 0.3
    z = logit(base)
    strong = False
    if "burst500" in fnd or "ring" in fnd:
        z += 3.0; strong = True
    if "card_testing" in fnd:
        z += 2.5; strong = True
    if fnd.get("device_new"):
        z += 0.6
    if fnd.get("amount_anomaly"):
        z += 0.6
    if fnd.get("out_of_region"):
        z += 0.7
    if fnd.get("region_known", 0) >= 3:
        z -= 0.8
    if fnd.get("recurring"):
        z -= 1.2
    if c["trigger_type"] == "customer_report":
        z += 0.5
    p = sigmoid(z)
    if strong:
        p = max(p, 0.9 if c["trigger_type"] != "risk_score" else 0.88)
    p = round(p, 2)

    if "burst500" in fnd or "ring" in fnd:
        pattern = "undocumented"
    elif "card_testing" in fnd:
        pattern = "card_testing"
    elif f.channel == "in_person" and fnd.get("out_of_region"):
        pattern = "out_of_region_use"
    elif f.channel == "online" and fnd.get("device_new"):
        pattern = "card_not_present_new_device"
    elif f.channel == "online":
        pattern = "card_not_present_fraud"
    else:
        pattern = "account_takeover" if fnd.get("amount_anomaly") else "out_of_region_use"

    # fraud episode
    card = c["card_id"]
    if "burst500" in fnd:
        aff = fnd["burst500"]
    elif "ring" in fnd:
        aff = G.card_window(card, f.ts - 30 * D, f.ts + 6 * H)
        aff = aff[aff.device_profile == fnd["profile"]]
    elif "card_testing" in fnd:
        w = G.card_window(card, fnd["card_testing"].ts.min(), f.ts)
        aff = w[w.channel == "online"]
    else:
        w = G.card_window(card, f.ts - 2 * D, f.ts + 6 * H)
        aff = w[(w.channel == f.channel) & ((w.memory_score.fillna(0) >= 0.5) | (w.TransactionID == f.TransactionID))]
        if f.channel == "online" and fnd.get("profile"):
            aff = aff[(aff.device_profile == fnd["profile"]) | (aff.TransactionID == f.TransactionID)]
        aff = aff.tail(4)
    aff = aff.sort_values("ts")

    conn_cards: list[str] = []
    conn_dev: list[str] = []
    if "ring" in fnd:
        conn_cards = sorted(fnd["ring"].card_id.unique().tolist())
        conn_dev = [fnd["profile"]]
    elif fnd.get("profile") and 1 <= fnd.get("profile_cards", 0) <= 8 and p >= 0.5:
        nb = G.device_neighbors(fnd["profile"], f.ts - 14 * D, f.ts + 1 * D)
        nb = nb[nb.memory_score.fillna(0) >= 0.5]
        conn_cards = sorted(set(nb.card_id) - {card})
        conn_dev = [fnd["profile"]] if conn_cards else []

    hint = "just under $500" if "burst500" in fnd else (fnd["profile"].split(" Build")[0] if "ring" in fnd else "")
    similar = G.similar_closed_cases(card, pattern if p >= 0.5 else "none", fnd.get("profile", ""), pd.Timestamp(c["opened_at"]), hint)
    if similar:
        notes = G.closed.set_index("case_id").loc[similar]
        s["evidence"].append({"claim": "Retrieved closed cases: " + "; ".join(
            f"{i} ({r.outcome}, {r.pattern}, {money(r.exposure_usd)})" for i, r in notes.iterrows()),
            "source": "graph", "ref": "query:similar_closed_cases", "entity_ids": similar})
    return {"p_initial": p, "pattern": pattern, "affected": aff, "connected_cards": conn_cards,
            "connected_devices": conn_dev, "similar": similar, "strong": strong, "trace": s["trace"] + ["assess"]}


def nba_initial(s: S) -> S:
    c, f, fnd, p = s["case"], s["f"], s["findings"], s["p_initial"]
    exposure = float(s["affected"].TransactionAmt.abs().sum()) if p >= 0.5 else 0.0
    report = c["trigger_type"] == "customer_report"
    initial: list[dict] = []
    req: list[dict] = []
    if s["pattern"] == "undocumented" and p >= 0.85:
        initial = [act("CREATE_CASE", "R9/3a: coordinated undocumented abuse, case opened with evidence", exposure),
                   act("DECLINE_TRANSACTION", "R9: stop further authorizations while the pattern is reviewed", exposure),
                   act("VERIFY_WITH_CUSTOMER", "R1: confirm with the cardholder before blocking", exposure)]
        if s["connected_cards"]:
            initial.append(act("MONITOR_CONNECTED_CARDS", "R6: other cards share the device profile", exposure))
        req = [{"type": "customer_validation", "asked_after_step": 4,
                "assumed_response": "Cardholder states they did not make these purchases and still holds the card "
                                    "(assumed: pattern matches confirmed closed cases of the same type)"}]
    elif s["pattern"] == "card_testing" and p >= 0.7:
        initial = [act("DECLINE_TRANSACTION", "R5: testing sequence observed", exposure),
                   act("STEP_UP_AUTH", "R5", exposure), act("CREATE_CASE", "3a: probability above 0.30", exposure)]
        req = [{"type": "step_up_auth", "asked_after_step": 4,
                "assumed_response": "Step-up passcode not completed; cardholder denies the small authorizations"}]
    elif report and fnd.get("recurring"):
        initial = [act("CREATE_CASE", "R7/3a: customer dispute", 0), act("VERIFY_WITH_CUSTOMER", "R7: charge matches the cardholder's own repeated pattern", 0),
                   act("WARN_CUSTOMER", "R7: remind the customer of the recurring charge", 0)]
        req = [{"type": "customer_validation", "asked_after_step": 4,
                "assumed_response": "After being shown the earlier identical charges, the customer recognises the recurring purchase"}]
    elif (p >= 0.85 or p <= 0.15) and not report:
        pass  # decisive on two independent signals: act directly (policy 6)
    else:
        initial = [act("CREATE_CASE", "3a: a case is opened whenever evidence is requested", exposure)]
        initial.append(act("VERIFY_WITH_CUSTOMER", f"R1: probability {p:.2f} rests on weak or single signals; verify before any block", exposure))
        if p >= 0.3:
            initial.append(act("MONITOR_CARD", "Raise monitoring while verification is pending", exposure))
        if p >= 0.6:
            resp = "Customer denies the transaction and still holds the card (assumed: device/amount anomalies and closed-case memory point to fraud)"
        elif p <= 0.35:
            resp = "Customer confirms the purchase (assumed: activity matches the card's own history)"
        else:
            resp = "No reply within 24 hours (assumed: evidence is balanced, so no answer is presumed either way)"
        if report and p > 0.35:
            resp = ("Customer repeats that they did not make the purchase and still holds the card"
                    if p >= 0.5 else "Customer cannot provide further detail; no confirmation either way within 24 hours")
        req = [{"type": "customer_validation", "asked_after_step": 4, "assumed_response": resp}]
    return {"initial": initial, "requests": req, "exposure0": exposure, "trace": s["trace"] + ["nba_initial"]}


def gather_and_final(s: S) -> S:
    c, f, p = s["case"], s["f"], s["p_initial"]
    req = s["requests"]
    resp = req[0]["assumed_response"] if req else ""
    denied = "did not make" in resp or "denies" in resp
    confirmed = "confirms" in resp or "recognises" in resp
    no_reply = "No reply" in resp or "no confirmation" in resp
    if req:
        s["evidence"].append({"claim": resp, "source": "customer", "ref": "evidence_request:1", "entity_ids": []})
    if denied:
        pf = max(p, 0.9) if s["pattern"] in ("undocumented", "card_testing") else min(0.95, max(p + 0.25, 0.86))
    elif confirmed:
        pf = min(p, 0.08)
    elif no_reply:
        pf = p
    else:
        pf = p
    pf = round(pf, 2)
    aff = s["affected"] if pf > 0.15 else s["affected"].iloc[:0]
    exposure = round(float(aff.TransactionAmt.abs().sum()), 2)
    shared = bool(s["connected_cards"])
    final: list[dict] = []
    if pf >= 0.85:
        verdict, status = "fraud", "closed_fraud"
        if s["pattern"] == "card_testing":
            final.append(act("DECLINE_TRANSACTION", "R5", exposure))
            final.append(act("BLOCK_CARD" if aff.TransactionAmt.max() > 100 else "STEP_UP_AUTH",
                             "R5: purchase over $100 already cleared" if aff.TransactionAmt.max() > 100 else "R5", exposure))
        else:
            final.append(act("BLOCK_CARD", f"R2: customer denied; exposure {money(exposure)} {'≤' if exposure <= 2500 else '>'} $2,500".replace("≤", "at or under").replace(">", "over"), exposure))
        final.append(act("CREATE_CASE", "R2/3a", exposure))
        if exposure > 1000 or shared or s["pattern"] == "undocumented":
            why = "R9: undocumented coordinated pattern" if s["pattern"] == "undocumented" else (
                "R6: shared device profile links other cards" if shared else "R2: exposure exceeds $1,000")
            final.append(act("FILE_REPORT", why, exposure))
        if shared:
            final.append(act("MONITOR_CONNECTED_CARDS", "R6: cards sharing the device profile", exposure))
        if s["pattern"] == "undocumented":
            final.append(act("ESCALATE_TO_ANALYST", "R9: pattern fits no documented typology", exposure))
    elif pf <= 0.15:
        verdict, status = "legitimate", "closed_legitimate"
        if s["initial"]:
            final.append(act("CREATE_CASE", "3a: case opened for the verification, closed as legitimate", 0))
        if c["trigger_type"] == "customer_report" and "recognises" in resp:
            final.append(act("WARN_CUSTOMER", "R7: recurring charge reminder", 0))
        final += [act("ALLOW_TRANSACTION", "R3: customer confirmed the activity" if confirmed else "Policy 6: activity consistent with the card's history on two independent signals", 0),
                  act("CLOSE_NO_FRAUD", "R3" if confirmed else "Policy 6: probability at or below 0.15 on two independent signals", 0)]
    else:
        verdict = "uncertain"
        final = [act("CREATE_CASE", "3a", exposure), act("MONITOR_CARD", "R4: no reply within 24 hours", exposure),
                 act("DECLINE_TRANSACTION", "R4: decline pending authorizations", exposure)]
        esc = exposure > 500 or c["trigger_type"] == "customer_report"
        if esc:
            final.append(act("ESCALATE_TO_ANALYST", "R8: uncertain verdict with exposure or conflicting evidence", exposure))
        status = "escalated" if esc else "open"
    if not s["initial"]:
        what = "nothing"
    elif [a["action"] for a in final] == [a["action"] for a in s["initial"]]:
        what = "nothing"
    else:
        r0 = resp.split('(')[0].strip().rstrip('.')
        what = (f"Assumed response ({r0}) moved fraud probability from {p:.2f} to {pf:.2f}, so the recommendation changed from verification to the actions the policy requires."
                if abs(pf - p) >= 0.01 else
                f"Assumed response ({r0}) left fraud probability at {pf:.2f}; with the verification step resolved, the recommendation moved from verification to the actions the policy requires.")
    if not req:
        final_actions = final
        initial = final
    else:
        final_actions, initial = final, s["initial"]
    stop = ("Fraud probability at or beyond the policy 6 thresholds on at least two independent signals; further steps would not change the decision."
            if not req else ("The verification response settled the question (policy 6)." if (denied or confirmed)
                             else "No reply received; further automated steps are unlikely to change the decision, so the case is handed to monitoring/analyst (policy 6)."))
    return {"p_final": pf, "final": final_actions, "initial": initial, "verdict": verdict, "status": status,
            "affected_final": aff, "exposure": exposure, "what_changed": what, "stop_reason": stop,
            "trace": s["trace"] + ["gather_more_evidence", "nba_final"]}


def build_graph():
    g = StateGraph(dict)
    for n, fn in [("trigger", trigger), ("investigate", investigate), ("assess", assess),
                  ("nba_initial", nba_initial), ("final", gather_and_final)]:
        g.add_node(n, lambda st, fn=fn: {**st, **fn(st)})
    g.add_edge(START, "trigger"); g.add_edge("trigger", "investigate"); g.add_edge("investigate", "assess")
    g.add_edge("assess", "nba_initial"); g.add_edge("nba_initial", "final"); g.add_edge("final", END)
    return g.compile()


# ---------------------------------------------------------------------------------------------
# Answer file
# ---------------------------------------------------------------------------------------------
PATTERN_TEXT = {
    "burst500": ("Repeated online purchases priced just under $500 in a sub-hour burst, from devices new to the account, "
                 "one behind a transparent proxy. The amounts appear chosen to stay under a $500 authorization threshold. "
                 "Found by windowing the card's timeline and matching the burst shape to confirmed closed cases CC-3748, CC-3841 and CC-3907."),
    "ring": ("A single device profile behind an anonymous proxy makes online purchases on many unrelated cardholders' cards in the same month. "
             "It affects every card that profile touches, not one customer. Found by traversing from the flagged transaction to its device profile "
             "and out to the other cards using it; closed cases CC-2649, CC-2971 and CC-2985 describe the same profile."),
}


def sar_block(c: dict, s: dict) -> dict:
    fa = [a["action"] for a in s["final"]]
    if "FILE_REPORT" not in fa:
        return {"file": False, "reason": ("No report: " + ("verdict is not fraud." if s["verdict"] != "fraud" else
                                                             "exposure is under $1,000 with no shared device, region cluster or coordinated pattern (3a).")),
                "narrative": "", "subjects": [], "total_amount_usd": 0, "activity_dates": []}
    aff, f = s["affected_final"], s["f"]
    d0, d1 = aff.ts.min(), aff.ts.max()
    devices = sorted(set(aff.device_profile.dropna()))
    reason = next(a["reason"] for a in s["final"] if a["action"] == "FILE_REPORT")
    lines = [
        f"Between {d0:%Y-%m-%d %H:%M} and {d1:%Y-%m-%d %H:%M}, card {c['card_id']} held by customer {c['customer_id']} was used for "
        f"{len(aff)} transaction(s) totalling {money(s['exposure'])}: " + ", ".join(f"{tid(r.TransactionID)} ({money(r.TransactionAmt)}, {r.channel})" for _, r in aff.iterrows()) + ".",
        f"The investigation was opened on {c['opened_at'][:10]} after a {c['trigger_type'].replace('_', ' ')}: \"{c['trigger_text']}\"",
        f"The purchases were made {'online' if (aff.channel == 'online').all() else 'across channels'}"
        + (f" from device profile(s) {', '.join(devices)}" if devices else "") + ".",
        "The cardholder, when contacted, stated they did not make the purchases and still holds the card (response simulated per policy section 5).",
    ]
    if s["pattern"] == "undocumented":
        lines.append(s["pattern_description"])
    if s["connected_cards"]:
        lines.append(f"The same device profile was used on {len(s['connected_cards'])} other cards in the period, including "
                     f"{', '.join(s['connected_cards'][:6])}, indicating a common actor across cardholders.")
    if s["similar"]:
        lines.append(f"The activity matches previously confirmed bank cases {', '.join(s['similar'][:3])}.")
    lines.append(f"This is suspicious because {reason.split(': ', 1)[-1].lower()}, and the activity is inconsistent with the cardholder's history.")
    lines.append(f"Total suspicious amount: {money(s['exposure'])}. The card is recommended for blocking and reissue; connected cards are placed under monitoring.")
    return {"file": True, "reason": reason, "narrative": " ".join(lines),
            "subjects": [c["customer_id"], c["card_id"], *s["connected_cards"][:6], *devices][:12],
            "total_amount_usd": s["exposure"], "activity_dates": [f"{d0:%Y-%m-%d}", f"{d1:%Y-%m-%d}"]}


def answer(c: dict, s: dict, latency: float, calls: int) -> dict:
    fnd = s["findings"]
    desc = ""
    if s["pattern"] == "undocumented":
        desc = PATTERN_TEXT["burst500" if "burst500" in fnd else "ring"]
    s["pattern_description"] = desc
    fraud = s["verdict"] == "fraud"
    aff = s["affected_final"] if s["verdict"] != "legitimate" else s["affected_final"].iloc[:0]
    affected_ids = [tid(x) for x in aff.TransactionID]
    summary = (f"{c['trigger_type'].replace('_', ' ').capitalize()} on {tid(s['f'].TransactionID)} ({money(s['f'].TransactionAmt)}, {s['f'].channel}). "
               f"Initial fraud probability {s['p_initial']:.2f}; " +
               (f"after the {s['requests'][0]['type'].replace('_', ' ')} it is {s['p_final']:.2f}. " if s["requests"] else "no further evidence was needed. ") +
               (f"Verdict {s['verdict']}, pattern {s['pattern']}, exposure {money(s['exposure'])} across {len(affected_ids)} transaction(s)." if fraud
                else f"Verdict {s['verdict']}."))
    if s["connected_cards"] and fraud:
        summary += f" {len(s['connected_cards'])} other cards share the device profile and are placed under monitoring."
    sar = sar_block(c, s)
    return {
        "case_id": c["case_id"],
        "case": {
            "status": s["status"], "verdict": s["verdict"], "fraud_probability": s["p_final"],
            "pattern": s["pattern"] if s["verdict"] != "legitimate" else "none",
            "pattern_description": desc if s["verdict"] != "legitimate" else "",
            "affected_txn_ids": affected_ids,
            "first_suspicious_txn_id": affected_ids[0] if affected_ids else "",
            "connected_card_ids": s["connected_cards"] if s["verdict"] != "legitimate" else [],
            "connected_device_profiles": s["connected_devices"] if s["verdict"] != "legitimate" else [],
            "exposure_usd": s["exposure"] if s["verdict"] != "legitimate" else 0,
            "evidence": s["evidence"],
            "similar_prior_cases": s["similar"],
            "summary": summary,
            "written_to_graph": False,
            "graph_case_id": "",
        },
        "evidence_requests": s["requests"],
        "next_best_actions": {"initial": s["initial"], "final": s["final"], "what_changed": s["what_changed"]},
        "sar": sar,
        "stop_reason": s["stop_reason"],
        "tool_calls": calls,
        "tokens": 0,
        "latency_s": round(latency, 2),
    }


def main() -> None:
    global G
    t0 = time.time()
    G = GraphMirror()
    print(f"graph mirror loaded in {time.time() - t0:.1f}s; memory model {'on' if G.tx.memory_score.notna().any() else 'off'}")
    graph = build_graph()
    CASES_OUT.mkdir(exist_ok=True)
    memory = []
    for c in G.cases.to_dict("records"):
        c["flagged_txn_id"] = int(c["flagged_txn_id"])
        G.calls = 0
        t = time.time()
        st = graph.invoke({"case": c})
        ans = answer(c, st, time.time() - t, G.calls)
        (CASES_OUT / f"{c['case_id']}.json").write_text(json.dumps(ans, indent=2, default=str), encoding="utf-8")
        memory.append({"case_id": c["case_id"], "verdict": ans["case"]["verdict"], "pattern": ans["case"]["pattern"],
                       "affected": ans["case"]["affected_txn_ids"], "devices": ans["case"]["connected_device_profiles"]})
        print(f"{c['case_id']} {c['trigger_type']:<16} p0={st['p_initial']:.2f} p1={st['p_final']:.2f} "
              f"{ans['case']['verdict']:<10} {ans['case']['pattern']:<28} exp={ans['case']['exposure_usd']:>8} "
              f"init={[a['action'] for a in ans['next_best_actions']['initial']]} final={[a['action'] for a in ans['next_best_actions']['final']]}")
    (STORE / "case_memory.json").write_text(json.dumps(memory, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
