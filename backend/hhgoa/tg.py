"""TigerGraph Savanna connection and loading for the HHGOA_IEEE graph.

    python -m hhgoa.tg schema     create vertex/edge types and the graph
    python -m hhgoa.tg load       export slim CSVs and load them through the loading job
    python -m hhgoa.tg queries    install the investigation queries
    python -m hhgoa.tg stats      vertex and edge counts
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from hhgoa.paths import BACKEND, REPO, STORE

GSQL_DIR = REPO / "tigergraph" / "hhgoa_ieee"
EXPORT = STORE / "tg_export"
GRAPH = "HHGOA_IEEE"


def env() -> dict[str, str]:
    out = {}
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def connect(graph: str | None = GRAPH):
    from pyTigerGraph import TigerGraphConnection

    e = env()
    conn = TigerGraphConnection(host=e["TG_HOST"], graphname=graph or "", gsqlSecret=e["TG_SECRET"], tgCloud=True)
    if graph:
        for attempt in range(6):  # workspace may be auto-resuming
            try:
                conn.getToken(e["TG_SECRET"])
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(20)
    return conn


def gsql_file(conn, path: Path) -> str:
    return conn.gsql(path.read_text(encoding="utf-8"))


def schema() -> None:
    conn = connect(None)
    print(gsql_file(conn, GSQL_DIR / "schema.gsql")[-1500:])


def export() -> dict[str, Path]:
    from hhgoa.agent import GraphMirror

    EXPORT.mkdir(parents=True, exist_ok=True)
    g = GraphMirror()
    tx = g.tx.reset_index(drop=True)
    cards = tx[["customer_id", "card_id", "card4", "card6"]].drop_duplicates("card_id")
    cards.to_csv(EXPORT / "cards.csv", index=False)
    t = pd.DataFrame({
        "txn_id": tx.TransactionID.astype(str), "ts": tx.ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
        "amount": tx.TransactionAmt, "product_cd": tx.ProductCD, "channel": tx.channel, "risk_score": tx.risk_score,
        "memory_score": tx.memory_score.fillna(0), "addr1": tx.addr1.map(lambda v: "" if pd.isna(v) else str(int(v))),
        "id_15": tx.id_15.fillna(""), "id_23": tx.id_23.fillna(""), "m4": tx.M4.fillna(""), "m6": tx.M6.fillna(""),
        "card_id": tx.card_id, "device_profile": tx.device_profile.fillna(""), "email": tx.P_emaildomain.fillna(""),
    })
    t.to_csv(EXPORT / "transactions.csv", index=False)
    s = tx.sort_values(["card_id", "ts"])[["card_id", "TransactionID"]]
    nxt = pd.DataFrame({"from_txn": s.TransactionID.astype(str).values[:-1], "to_txn": s.TransactionID.astype(str).values[1:]})
    nxt = nxt[s.card_id.values[:-1] == s.card_id.values[1:]]
    nxt.to_csv(EXPORT / "next.csv", index=False)
    cc = g.closed.copy()
    cc["opened_at"] = cc.opened_at.dt.strftime("%Y-%m-%d %H:%M:%S")
    cc[["case_id", "outcome", "pattern", "exposure_usd", "report_filed", "opened_at", "actions_taken", "analyst_notes", "card_id"]].to_csv(EXPORT / "closed_cases.csv", index=False)
    ct = cc.assign(txn_id=cc.txn_ids.astype(str).str.split("|")).explode("txn_id")[["case_id", "txn_id"]]
    ct.to_csv(EXPORT / "case_txns.csv", index=False)
    cn = cc.assign(card=cc.connected_card_ids.fillna("").astype(str).str.split("|")).explode("card")
    cn = cn[cn.card != ""][["case_id", "card"]].rename(columns={"card": "card_id"})
    cn.to_csv(EXPORT / "case_conn.csv", index=False)
    return {"f_cards": EXPORT / "cards.csv", "f_txns": EXPORT / "transactions.csv", "f_next": EXPORT / "next.csv",
            "f_cases": EXPORT / "closed_cases.csv", "f_case_txns": EXPORT / "case_txns.csv", "f_case_conn": EXPORT / "case_conn.csv"}


def load() -> None:
    names = {"f_cards": "cards.csv", "f_txns": "transactions.csv", "f_next": "next.csv", "f_cases": "closed_cases.csv",
             "f_case_txns": "case_txns.csv", "f_case_conn": "case_conn.csv"}
    files = {k: EXPORT / v for k, v in names.items()}
    if not all(p.exists() for p in files.values()):
        files = export()
    conn = connect()
    print(conn.gsql(f"USE GRAPH {GRAPH}\nDROP JOB load_hhgoa")[-200:])
    print(gsql_file(conn, GSQL_DIR / "load_job.gsql")[-400:])
    for tag, path in files.items():
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        chunk = 60_000
        for i in range(0, len(df), chunk):
            part = STORE / "tg_export" / f"_part_{tag}.csv"
            df.iloc[i:i + chunk].to_csv(part, index=False)
            for attempt in range(4):
                try:
                    res = conn.runLoadingJobWithFile(str(part), tag, "load_hhgoa", sep=",", timeout=600_000)
                    break
                except Exception as exc:
                    if attempt == 3:
                        raise
                    print("  retry", tag, i, str(exc)[:120])
                    time.sleep(10)
            stats = res[0]["statistics"] if isinstance(res, list) and res else res
            print(f"{tag} rows {i}-{min(i + chunk, len(df))}: ok", str(stats)[:160] if i == 0 else "")


def queries() -> None:
    conn = connect()
    print(gsql_file(conn, GSQL_DIR / "queries.gsql")[-1500:])


def stats() -> None:
    conn = connect()
    print(conn.getVertexCount("*"))
    print(conn.getEdgeCount("*"))


if __name__ == "__main__":
    {"schema": schema, "load": load, "queries": queries, "stats": stats}[sys.argv[1]]()
