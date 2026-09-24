"""Convert the HHGOA_IEEE CSVs into compact Parquet files the agent loads in seconds.

    python -m hhgoa.prepare            (run from backend/)
"""

from __future__ import annotations

import time

import pandas as pd

from hhgoa.paths import DATASET, STORE

TXN_COLS = [
    "TransactionID", "TransactionDT", "TransactionAmt", "ProductCD",
    "card1", "card2", "card3", "card4", "card5", "card6", "addr1", "addr2", "dist1", "dist2",
    "P_emaildomain", "R_emaildomain", "C1", "C2", "C13", "C14", "D1", "D10", "D15",
    "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
    "customer_id", "ts", "channel", "risk_score",
]
ID_COLS = ["TransactionID", "id_15", "id_23", "id_30", "id_31", "id_33", "id_34", "DeviceType", "DeviceInfo"]


def main() -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    tx = pd.read_csv(DATASET / "transactions.csv", usecols=TXN_COLS, low_memory=False)
    tx["ts"] = pd.to_datetime(tx["ts"])
    ident = pd.read_csv(DATASET / "identity.csv", usecols=ID_COLS, low_memory=False)
    tx = tx.merge(ident, on="TransactionID", how="left")
    tx.to_parquet(STORE / "transactions.parquet", index=False)
    pd.read_csv(DATASET / "closed_cases_history.csv").to_parquet(STORE / "closed_cases.parquet", index=False)
    pd.read_csv(DATASET / "case_pack.csv").to_parquet(STORE / "case_pack.parquet", index=False)
    print(f"{len(tx):,} transactions, {ident.shape[0]:,} identity rows -> {STORE} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
