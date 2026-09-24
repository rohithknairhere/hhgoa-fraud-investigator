"""Learn a fraud classifier from the bank's closed cases (case memory) and score every transaction.

Labels come only from closed_cases_history.csv (Jul-Oct): a transaction is positive if it is
listed in a confirmed-fraud case. Features are Vesta's anonymized columns (V, C, D, M, card,
address, amount, product). Output: .store/memory_scores.parquet (TransactionID, memory_score).
Run with a Python that has lightgbm:  python hhgoa/train_memory_model.py
"""

import time
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
ROOT = r"C:\Users\Rohith\Desktop\err\Projects\TigerGraph"
t0 = time.time()
tx = pd.read_csv(ROOT + r"\dataset\transactions.csv", low_memory=False)
cc = pd.read_csv(ROOT + r"\dataset\closed_cases_history.csv")
pos = set(int(t) for s in cc[cc.outcome == "confirmed_fraud"].txn_ids for t in str(s).split("|"))
tx["ts"] = pd.to_datetime(tx["ts"])
tx["y"] = tx.TransactionID.isin(pos).astype(int)
drop = {"TransactionID", "TransactionDT", "customer_id", "ts", "risk_score", "y", "card1"}
for c in tx.columns:
    if not pd.api.types.is_numeric_dtype(tx[c]) and c not in drop:
        tx[c] = tx[c].astype("category")
feats = [c for c in tx.columns if c not in drop]
train = tx[tx.ts < "2016-10-01"]
valid = tx[(tx.ts >= "2016-10-01") & (tx.ts < "2016-11-01")]
params = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.5, verbose=-1)
m = lgb.LGBMClassifier(**params).fit(train[feats], train.y)
print("valid AUC", round(roc_auc_score(valid.y, m.predict_proba(valid[feats])[:, 1]), 4),
      "| risk_score AUC", round(roc_auc_score(valid.y, valid.risk_score), 4))
full = tx[tx.ts < "2016-11-01"]
m = lgb.LGBMClassifier(**params).fit(full[feats], full.y)
out = pd.DataFrame({"TransactionID": tx.TransactionID, "memory_score": np.round(m.predict_proba(tx[feats])[:, 1], 4)})
out.to_parquet(ROOT + r"\backend\.store\memory_scores.parquet", index=False)
print("done in", round(time.time() - t0), "s; base rate", round(tx.y.mean(), 4))
