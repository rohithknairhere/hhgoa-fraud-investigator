"""Autonomous monitoring of the exam period (November and December), beyond the 20 benchmark cases.

Runs two graph queries through the TigerGraph MCP server:
  device_ring_components  connected components over cards and proxied device profiles (a GSQL graph algorithm)
  threshold_bursts        cards with three or more online purchases between $450 and $500 from a new device inside an hour
and writes one alert file per finding to <repo>/monitoring/.

    python -m hhgoa.monitor      (run from backend/)
"""

from __future__ import annotations

import json

import pandas as pd

from hhgoa.paths import REPO, STORE
from hhgoa.tg_source import TigerGraphSource, _rows

OUT = REPO / "monitoring"
WINDOW = ("2016-11-01 00:00:00", "2016-12-31 23:59:59")


def payload_block(payload: dict) -> dict:
    data = payload.get("data")
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    merged: dict = {}
    for block in data or []:
        if isinstance(block, dict):
            merged.update(block)
    return merged


def main() -> None:
    cases = pd.read_parquet(STORE / "case_pack.parquet")
    bench_cards = set(cases.card_id)
    src = TigerGraphSource(cases)
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()
    alerts = []

    comp = payload_block(src.q("device_ring_components", t0=WINDOW[0], t1=WINDOW[1], iterations=12))
    for label, cards in sorted(comp.get("cards", {}).items(), key=lambda kv: -len(kv[1])):
        if len(cards) < 5:
            continue
        devices = sorted(comp.get("devices", {}).get(label, []))
        key = devices[0].split(" Build")[0].split(" | ")[0] if devices else ""
        memory = [c["case_id"] for c in src._cases(src.q("closed_cases_by_note", phrase=key, before_ts=WINDOW[0], k=5))] if key else []
        alerts.append({
            "alert_id": f"MON-RING-{len(alerts) + 1:02d}",
            "type": "shared_device_ring",
            "pattern": "undocumented",
            "description": (f"{len(cards)} cards are connected through {len(devices)} device profile(s) used behind an anonymous "
                            f"or hidden proxy between {comp['first_ts'].get(label, '')[:10]} and {comp['last_ts'].get(label, '')[:10]}: "
                            f"{comp['txns'].get(label, 0)} transactions totalling ${comp['amount'].get(label, 0):,.2f}."),
            "method": "Weakly connected components over the card and device-profile graph, restricted to proxied transactions on device profiles that name a specific device model (query: device_ring_components).",
            "card_ids": sorted(cards),
            "device_profiles": devices,
            "transactions": comp["txns"].get(label, 0),
            "amount_usd": round(comp["amount"].get(label, 0), 2),
            "benchmark_cases_touched": sorted(cases[cases.card_id.isin(cards)].case_id),
            "closed_case_memory": memory,
            "recommended_actions": [
                {"action": "CREATE_CASE", "route": "auto", "reason": "R6: shared origin across cards"},
                {"action": "MONITOR_CONNECTED_CARDS", "route": "auto", "reason": "R6: every card sharing the device profile"},
                {"action": "ESCALATE_TO_ANALYST", "route": "auto", "reason": "R9: coordinated activity outside the documented patterns"},
                {"action": "FILE_REPORT", "route": "L2", "reason": "R6/R9: file once an analyst confirms fraud on the shared device"},
            ],
        })

    bursts = payload_block(src.q("threshold_bursts", t0=WINDOW[0], t1=WINDOW[1], min_txns=3)).get("cards", [])
    burst_memory = [c["case_id"] for c in src._cases(src.q("closed_cases_by_note", phrase="just under $500", before_ts=WINDOW[0], k=3))]
    for card in sorted(bursts):
        memory = burst_memory
        alerts.append({
            "alert_id": f"MON-BURST-{len(alerts) + 1:02d}",
            "type": "threshold_evasion_burst",
            "pattern": "undocumented",
            "description": f"Card {card} made three or more online purchases between $450 and $500 within one hour, from a device new to the account.",
            "method": "Per-card sliding one-hour window over online transactions (query: threshold_bursts).",
            "card_ids": [card],
            "benchmark_cases_touched": sorted(cases[cases.card_id == card].case_id),
            "closed_case_memory": memory,
            "recommended_actions": [
                {"action": "CREATE_CASE", "route": "auto", "reason": "3a: pattern matches confirmed closed cases"},
                {"action": "VERIFY_WITH_CUSTOMER", "route": "auto", "reason": "R1: confirm with the cardholder before blocking"},
                {"action": "MONITOR_CARD", "route": "auto", "reason": "Raise monitoring while verification is pending"},
            ],
        })

    for a in alerts:
        (OUT / f"{a['alert_id']}.json").write_text(json.dumps(a, indent=2), encoding="utf-8")
    summary = {"window": WINDOW, "alerts": len(alerts),
               "rings": sum(a["type"] == "shared_device_ring" for a in alerts),
               "bursts": sum(a["type"] == "threshold_evasion_burst" for a in alerts),
               "graph_calls": src.calls}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(summary)
    for a in alerts[:12]:
        print(a["alert_id"], a["description"][:140], "| bench:", a["benchmark_cases_touched"])
    src.mcp.close()


if __name__ == "__main__":
    main()
