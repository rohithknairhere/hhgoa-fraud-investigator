"""Export the deterministic HHGOA graph as CSVs for tigergraph/load.gsql."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.scenarios import build_dataset  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def export(out: Path) -> dict[str, int]:
    store = build_dataset().store
    out.mkdir(parents=True, exist_ok=True)

    def neighbour(vid: str, vtype: str) -> str:
        ids = store.neighbors(vid, vtype)
        return ids[0] if ids else ""

    tables: dict[str, tuple[list[str], list[list]]] = {
        "customers.csv": (["customer_id", "tenure_days", "addr1", "p_emaildomain", "kyc_level", "segment"], []),
        "cards.csv": (["card_id", "card1", "card4", "card6", "issuer_country", "customer_id"], []),
        "devices.csv": (["device_id", "device_type", "device_info"], []),
        "ips.csv": (["ip_id", "country", "is_proxy", "asn"], []),
        "transactions.csv": (["txn_id", "amount", "ts", "product_cd", "is_fraud", "chargeback",
                              "card_id", "device_id", "ip_id", "customer_id"], []),
        "cases.csv": (["case_id", "status", "pattern_tags", "outcome", "summary", "decision", "opened_ts",
                       "sar_filed", "customer_id"], []),
        "case_transactions.csv": (["case_id", "txn_id"], []),
    }
    for v in sorted(store.vertices.values(), key=lambda v: v["id"]):
        t, vid = v["type"], v["id"]
        if t == "Customer":
            tables["customers.csv"][1].append([vid, v["tenure_days"], v["addr1"], v["p_emaildomain"],
                                               v["kyc_level"], v["segment"]])
        elif t == "Card":
            tables["cards.csv"][1].append([vid, v["card1"], v["card4"], v["card6"], v["issuer_country"],
                                           neighbour(vid, "Customer")])
        elif t == "Device":
            tables["devices.csv"][1].append([vid, v["device_type"], v["device_info"]])
        elif t == "IP":
            tables["ips.csv"][1].append([vid, v["country"], str(v["is_proxy"]).lower(), v["asn"]])
        elif t == "Transaction":
            tables["transactions.csv"][1].append([
                vid, v["amount"], v["ts"], v["product_cd"], v["is_fraud"], str(v["chargeback"]).lower(),
                neighbour(vid, "Card"), neighbour(vid, "Device"), neighbour(vid, "IP"), neighbour(vid, "Customer")])
        elif t == "Case":
            tables["cases.csv"][1].append([vid, v["status"], "|".join(v.get("pattern_tags") or []), v["outcome"],
                                           v.get("summary", ""), v.get("decision", ""), v.get("opened_ts", 0),
                                           str(v.get("sar_filed", False)).lower(), neighbour(vid, "Customer")])
            for txn in sorted(store.neighbors(vid, "Transaction")):
                tables["case_transactions.csv"][1].append([vid, txn])

    counts = {}
    for name, (header, rows) in tables.items():
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        counts[name] = len(rows)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPO / "tigergraph" / "data")
    args = parser.parse_args()
    for name, n in export(args.out).items():
        print(f"{name:<24} {n:>6} rows")
