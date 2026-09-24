"""Turn MCP tool results into weighted, explainable risk signals.

Every signal carries the graph element ids and evidence ids that justify it,
so the final decision can cite exactly what was retrieved from TigerGraph.
Weights are log-odds contributions; positive = fraud-leaning.
"""

from __future__ import annotations

from typing import Any

IDENTITY = "identity_verification"
RELATIONSHIP = "relationship_validation"
ANALYST = "analyst_review"


def _signal(name: str, weight: float, strength: float, description: str, evidence: list[str],
            elements: list[str], needs: str | None = None, tag: str | None = None) -> dict[str, Any]:
    strength = round(max(0.0, min(1.0, strength)), 3)
    return {
        "name": name,
        "weight": weight,
        "strength": strength,
        "contribution": round(weight * strength, 3),
        "direction": "fraud" if weight > 0 else "legitimate",
        "needs_verification": needs,
        "pattern_tag": tag,
        "description": description,
        "evidence_ids": evidence,
        "graph_elements": elements,
    }


def extract_graph_signals(results: dict[str, Any], evidence_ids: dict[str, str]) -> list[dict[str, Any]]:
    """`results` keys: context, history, related_device, related_ip, related_customer, similar."""
    ctx = results["context"]
    hist = results.get("history") or {}
    stats = ctx["stats"]
    txn, card, dev, ip, cust = ctx["transaction"], ctx["card"], ctx["device"], ctx["ip"], ctx["customer"]
    E = evidence_ids
    out: list[dict[str, Any]] = []

    n_dev_cards = stats["device_distinct_cards"]
    if n_dev_cards >= 3:
        out.append(_signal(
            "device_sharing", 2.2, (n_dev_cards - 2) / 5,
            f"Device {dev['id']} ({dev['device_info']}) has been used by {n_dev_cards} distinct cards "
            f"across {stats['device_distinct_customers']} customers.",
            [E["context"], E.get("related_device", E["context"])], [dev["id"], *stats["device_cards"]],
            needs=RELATIONSHIP, tag="device_sharing"))

    n_ip_cards = stats["ip_distinct_cards"]
    if n_ip_cards >= 4:
        out.append(_signal(
            "ip_cluster", 1.8, (n_ip_cards - 3) / 5,
            f"IP {ip['id']} ({ip['country']}, {ip['asn']}) is shared by {n_ip_cards} cards / "
            f"{stats['ip_distinct_customers']} customers.",
            [E["context"], E.get("related_ip", E["context"])], [ip["id"]], tag="ip_cluster"))

    vel = stats["card_txn_count_1h"]
    if vel >= 6:
        out.append(_signal(
            "velocity_burst", 2.0, (vel - 5) / 8,
            f"Card {card['id']} made {vel} transactions (${stats['card_amount_1h']:,.2f}) in the hour before this one.",
            [E["context"]], [card["id"], txn["id"]], needs=IDENTITY, tag="velocity_burst"))

    if len(stats["card_countries_1h"]) > 1:
        out.append(_signal(
            "impossible_travel", 2.0, 1.0,
            f"Card {card['id']} was used from {', '.join(stats['card_countries_1h'])} within one hour.",
            [E["context"]], [card["id"], ip["id"]], tag="impossible_travel"))

    near = stats["near_threshold_count_24h"]
    if near >= 3:
        out.append(_signal(
            "structuring", 2.2, (near - 2) / 5,
            f"{near} transactions between $9,000 and $10,000 in 24h totalling "
            f"${stats['customer_amount_24h']:,.2f}, consistent with structuring below reporting thresholds.",
            [E["context"]], [cust["id"], card["id"]], tag="structuring"))

    if "emulator" in str(dev.get("device_info", "")).lower():
        out.append(_signal(
            "emulator_device", 1.5, 1.0, f"Device fingerprint reports '{dev['device_info']}'.",
            [E["context"]], [dev["id"]], tag="bot_device"))

    if ip.get("is_proxy"):
        out.append(_signal(
            "proxy_ip", 0.8, 1.0, f"Transaction routed through proxy/hosting ASN {ip['asn']} ({ip['country']}).",
            [E["context"]], [ip["id"]], needs=IDENTITY))

    has_history = bool(hist.get("txn_count"))
    tenure = cust.get("tenure_days", 0)
    if not has_history and tenure < 14:
        out.append(_signal(
            "new_customer", 0.5, 1.0, f"Customer {cust['id']} is {tenure} days old with no prior baseline.",
            [E["context"], E.get("history", E["context"])], [cust["id"]], needs=IDENTITY, tag="new_customer"))

    if has_history:
        known_devices = set(hist.get("known_device_ids", []))
        if dev["id"] in known_devices:
            out.append(_signal(
                "known_device", -0.9, 1.0, f"Device {dev['id']} appears in the customer's baseline history.",
                [E["history"]], [dev["id"], cust["id"]]))
        else:
            out.append(_signal(
                "new_device", 0.7, 1.0,
                f"Device {dev['id']} has never been used by customer {cust['id']} "
                f"(known devices: {', '.join(sorted(known_devices)) or 'none'}).",
                [E["history"], E["context"]], [dev["id"], cust["id"]], needs=IDENTITY))

        countries = set(hist.get("known_ip_countries", []))
        if ip["country"] in countries and not ip.get("is_proxy"):
            out.append(_signal(
                "known_geo", -0.4, 1.0, f"{ip['country']} matches the customer's usual locations.",
                [E["history"]], [ip["id"]]))
        elif ip["country"] not in countries and not ip.get("is_proxy") and len(stats["card_countries_1h"]) <= 1:
            out.append(_signal(
                "new_geo", 0.6, 1.0,
                f"First activity from {ip['country']} (usual: {', '.join(sorted(countries)) or 'none'}).",
                [E["history"], E["context"]], [ip["id"]], needs=IDENTITY, tag="geo_anomaly"))

        avg = hist.get("avg_amount") or 0
        if avg and txn["amount"] / avg >= 3:
            ratio = txn["amount"] / avg
            out.append(_signal(
                "amount_anomaly", 1.0, (ratio - 2) / 6,
                f"${txn['amount']:,.2f} is {ratio:.1f}x the customer's average of ${avg:,.2f}.",
                [E["history"], E["context"]], [txn["id"], cust["id"]], needs=IDENTITY))

        dormant = hist.get("days_since_last_txn")
        if dormant is not None and dormant > 180 and tenure > 365:
            out.append(_signal(
                "dormant_reactivation", 0.9, 1.0, f"Account inactive for {dormant:.0f} days before this transaction.",
                [E["history"]], [cust["id"]], needs=IDENTITY, tag="dormant_reactivation"))

        cbs = hist.get("chargeback_count", 0)
        if cbs >= 2:
            out.append(_signal(
                "prior_chargebacks", 1.0, cbs / 4,
                f"Customer has {cbs} chargebacks in the lookback window.",
                [E["history"]], [cust["id"]], needs=ANALYST, tag="first_party"))
        elif tenure >= 365 and cbs == 0:
            out.append(_signal(
                "established_customer", -1.2, 1.0,
                f"Customer tenure {tenure} days, {hist['txn_count']} clean transactions, no chargebacks.",
                [E["history"]], [cust["id"]]))

    # Neighbourhood fraud (labels + confirmed cases within 2 hops of device / IP).
    fraud_txns = set(stats.get("fraud_labeled_neighbor_txns", []))
    confirmed: set[str] = set()
    for key in ("related_device", "related_ip", "related_customer"):
        rel = results.get(key)
        if rel:
            fraud_txns.update(rel.get("fraud_transactions", []))
            confirmed.update(rel.get("confirmed_fraud_cases", []))
    if fraud_txns or confirmed:
        n = len(fraud_txns) + 2 * len(confirmed)
        refs = [E[k] for k in ("context", "related_device", "related_ip", "related_customer") if k in E]
        out.append(_signal(
            "fraud_neighbourhood", 1.8, n / 6,
            f"{len(fraud_txns)} fraud-labelled transactions and {len(confirmed)} confirmed fraud cases "
            f"within two hops of this transaction's card/device/IP.",
            refs, sorted(fraud_txns | confirmed)))

    # Synthetic identity: thin-file customers sharing the same address within the neighbourhood.
    rel_c = results.get("related_customer") or {}
    peers = [e for e in rel_c.get("entities", [])
             if e.get("type") == "Customer" and e["id"] != cust["id"]
             and e.get("addr1") == cust.get("addr1") and e.get("tenure_days", 9999) < 60]
    if len(peers) >= 2 and tenure < 60:
        out.append(_signal(
            "synthetic_identity", 1.6, len(peers) / 4,
            f"{len(peers)} other thin-file customers (<60 days) share address {cust.get('addr1')} "
            f"and devices/IPs with {cust['id']}.",
            [E["related_customer"]], [cust["id"], *sorted(p["id"] for p in peers)],
            needs=RELATIONSHIP, tag="synthetic_identity"))

    return out


def derive_pattern_tags(signals: list[dict[str, Any]]) -> list[str]:
    tags = {s["pattern_tag"] for s in signals if s.get("pattern_tag")}
    ato = {"new_device", "proxy_ip", "amount_anomaly"} & {s["name"] for s in signals}
    if len(ato) >= 2:
        tags.add("account_takeover")
    return sorted(tags)


def precedent_signal(similar: dict[str, Any], evidence_id: str) -> dict[str, Any] | None:
    cases = [c for c in similar.get("cases", []) if c["similarity"] >= 0.3][:3]
    if not cases:
        return None
    total = sum(c["similarity"] for c in cases)
    fraud_rate = sum(c["similarity"] for c in cases if c["outcome"] == "confirmed_fraud") / total
    strength = total / len(cases)
    outcomes = ", ".join(f"{c['case_id']} ({c['outcome']}, sim {c['similarity']:.2f})" for c in cases)
    return _signal(
        "similar_case_precedent", round(1.2 * (2 * fraud_rate - 1), 3), strength,
        f"Closest closed cases: {outcomes}; {fraud_rate:.0%} similarity-weighted fraud rate.",
        [evidence_id], [c["case_id"] for c in cases])


def followup_signal(item: dict[str, Any], evidence_id: str) -> dict[str, Any]:
    return _signal(item["signal"], item["weight"], item.get("strength", 1.0), item["description"],
                   [evidence_id], [], needs=None)
