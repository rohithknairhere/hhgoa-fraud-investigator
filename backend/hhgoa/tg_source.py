"""Graph access for the agent through the official TigerGraph MCP server (tigergraph-mcp).

The server is launched over stdio with a tool allowlist (the agent's permissions):
  run_installed_query  read: the investigation queries in tigergraph/hhgoa_ieee/queries.gsql
  add_node, add_edge   write: InvestigationCase vertices and their edges (case memory)
  get_node             read: verify a written case
The agent never sends free-form GSQL.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import pandas as pd

from hhgoa.paths import BACKEND
from hhgoa.tg import env

ALLOWED_TOOLS = "run_installed_query,get_node,add_node,add_edge"
TX_COLS = {"txn_id": "TransactionID", "amount": "TransactionAmt", "product_cd": "ProductCD", "m4": "M4", "m6": "M6",
           "email": "P_emaildomain"}


class MCPBridge:
    """Runs an MCP client session on a background event loop so the sync agent can call tools."""

    def __init__(self) -> None:
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        e = env()
        exe = BACKEND / ".venv" / "Scripts" / "tigergraph-mcp.exe"
        if not exe.exists():
            exe = BACKEND / ".venv" / "bin" / "tigergraph-mcp"
        self.params = StdioServerParameters(command=str(exe), args=[], env={
            **os.environ, "TG_HOST": e["TG_HOST"], "TG_SECRET": e["TG_SECRET"],
            "TG_GRAPHNAME": e.get("TG_GRAPH", "HHGOA_IEEE"), "TG_ALLOWED_TOOLS": ALLOWED_TOOLS})
        self._Client = Client
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.client = None
        self.tools: list[str] = []
        self._call(self._open())

    async def _open(self) -> None:
        self._cm = self._Client(self.params, read_timeout_seconds=300)
        self.client = await self._cm.__aenter__()
        self.tools = [t.name for t in (await self.client.list_tools()).tools]

    def _call(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=600)

    def tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        full = f"tigergraph__{name}"
        if full not in self.tools:
            raise PermissionError(f"tool {full} is not in the agent's allowlist")

        async def run():
            return await self.client.call_tool(full, args)

        res = self._call(run())
        text = "".join(getattr(c, "text", "") for c in res.content)
        start = text.find("{")
        payload, _ = json.JSONDecoder().raw_decode(text[start:]) if start >= 0 else ({"success": False, "summary": text[:200]}, 0)
        if not payload.get("success", True):
            raise RuntimeError(payload.get("summary", "tool failed"))
        return payload

    def close(self) -> None:
        try:
            self._call(self._cm.__aexit__(None, None, None))
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)


def _rows(payload: dict[str, Any], key: str = "txns") -> list[dict]:
    data = payload.get("data")
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    for block in data or []:
        if isinstance(block, dict) and key in block:
            return block[key]
    return []


def _tx_frame(rows: list[dict]) -> pd.DataFrame:
    recs = []
    for r in rows:
        a = {k.split(".")[-1]: v for k, v in (r.get("attributes") or {}).items()}
        recs.append(a)
    df = pd.DataFrame(recs)
    if df.empty:
        return pd.DataFrame(columns=["TransactionID", "ts", "TransactionAmt", "ProductCD", "channel", "risk_score",
                                     "memory_score", "addr1", "id_15", "id_23", "M4", "M6", "card_id", "device_profile",
                                     "P_emaildomain"])
    df = df.rename(columns=TX_COLS)
    df["TransactionID"] = df.TransactionID.astype(int)
    df["ts"] = pd.to_datetime(df.ts)
    df["addr1"] = pd.to_numeric(df.get("addr1"), errors="coerce")
    for c in ("id_15", "id_23", "M4", "M6", "device_profile", "P_emaildomain", "card_id"):
        if c in df:
            df[c] = df[c].replace("", pd.NA)
    return df.sort_values("ts").reset_index(drop=True)


class TigerGraphSource:
    """Same interface as the local GraphMirror, answered by TigerGraph installed queries via MCP."""

    name = "tigergraph"

    def __init__(self, cases: pd.DataFrame) -> None:
        self.mcp = MCPBridge()
        self.cases = cases
        self.calls = 0
        self.closed_cache: dict[str, dict] = {}

    def q(self, query: str, **params) -> dict:
        self.calls += 1
        return self.mcp.tool("run_installed_query", {"query_name": query, "params": params})

    @staticmethod
    def _ts(t) -> str:
        return pd.Timestamp(t).strftime("%Y-%m-%d %H:%M:%S")

    def get_transaction(self, txn_id: int) -> pd.Series:
        df = _tx_frame(_rows(self.q("get_txn", txn=str(txn_id))))
        return df.iloc[0]

    def card_window(self, card_id: str, start, end) -> pd.DataFrame:
        df = _tx_frame(_rows(self.q("card_window", card=card_id, t0=self._ts(start), t1=self._ts(end))))
        df["card_id"] = card_id
        return df

    def card_history(self, card_id: str, before) -> pd.DataFrame:
        return self.card_window(card_id, "2016-01-01", pd.Timestamp(before) - pd.Timedelta(seconds=1))

    def device_neighbors(self, profile: str, start, end) -> pd.DataFrame:
        df = _tx_frame(_rows(self.q("device_neighbors", profile=profile, t0=self._ts(start), t1=self._ts(end))))
        df["device_profile"] = profile
        return df

    def _cases(self, payload: dict) -> list[dict]:
        out = []
        for v in _rows(payload, "cases"):
            a = v.get("attributes", {})
            rec = {"case_id": v["v_id"], "outcome": a.get("outcome"), "pattern": a.get("pattern"),
                   "exposure_usd": a.get("exposure_usd"), "analyst_notes": a.get("analyst_notes", ""),
                   "opened_at": a.get("opened_at")}
            self.closed_cache[rec["case_id"]] = rec
            out.append(rec)
        return out

    def similar_closed_cases(self, card_id: str, pattern: str, device_hint: str, before, note_hint: str = "") -> list[str]:
        b = self._ts(before)
        if note_hint:
            hit = self._cases(self.q("closed_cases_by_note", phrase=note_hint, before_ts=b, k=5))
            if hit:
                return [c["case_id"] for c in hit]
        same = sorted(self._cases(self.q("closed_cases_for_card", card=card_id, before_ts=b)),
                      key=lambda c: c["opened_at"] or "", reverse=True)
        out = [c["case_id"] for c in same if c["pattern"] == pattern][:2] + [c["case_id"] for c in same][:2]
        if device_hint:
            key = device_hint.split(" Build")[0].split(" | ")[0].strip()
            if key and len(key) > 3:
                out += [c["case_id"] for c in self._cases(self.q("closed_cases_by_note", phrase=key, before_ts=b, k=3))]
        if pattern not in ("none", ""):
            out += [c["case_id"] for c in self._cases(self.q("closed_cases_by_pattern", pattern=pattern, before_ts=b, k=1))]
        seen: list[str] = []
        for x in out:
            if x not in seen:
                seen.append(x)
        return seen[:5]

    def closed_info(self, ids: list[str]) -> list[dict]:
        return [self.closed_cache[i] for i in ids if i in self.closed_cache]

    def prior_investigations(self, profile: str) -> list[dict]:
        if not profile:
            return []
        out = []
        for v in _rows(self.q("investigations_for_device", profile=profile), "cases"):
            out.append({"case_id": v["v_id"], **{k: v.get("attributes", {}).get(k) for k in ("verdict", "pattern", "status")}})
        return out

    def search_knowledge(self, qv: list[float], k: int = 6, sources: list[str] | None = None) -> list[dict]:
        rows = _rows(self.q("search_knowledge", qv=qv, sources=sources or [], k=k), "chunks")
        return [{k2.split(".")[-1]: v for k2, v in r.get("attributes", {}).items()} for r in rows]

    def write_case(self, answer: dict, card_id: str, flagged: str, opened_at: str) -> str:
        c = answer["case"]
        gid = f"INV-{answer['case_id']}"
        self.mcp.tool("add_node", {"vertex_type": "InvestigationCase", "vertex_id": gid, "attributes": {
            "status": c["status"], "verdict": c["verdict"], "fraud_probability": c["fraud_probability"],
            "pattern": c["pattern"], "exposure_usd": c["exposure_usd"], "summary": c["summary"][:2000],
            "sar_filed": bool(answer["sar"]["file"]),
            "final_actions": ",".join(a["action"] for a in answer["next_best_actions"]["final"]),
            "opened_at": opened_at}})
        edges = [("CASE_FLAGS", "Transaction", flagged), ("CASE_ON_CARD", "Card", card_id)]
        edges += [("CASE_AFFECTS", "Transaction", t) for t in c["affected_txn_ids"]]
        edges += [("CASE_CITES", "ClosedCase", x) for x in c["similar_prior_cases"]]
        edges += [("CASE_LINKS_CARD", "Card", x) for x in c["connected_card_ids"][:40]]
        edges += [("CASE_DEVICE", "DeviceProfile", d) for d in (c["connected_device_profiles"] or answer.get("_devices", []))]
        for etype, ttype, tid in edges:
            self.mcp.tool("add_edge", {"source_vertex_type": "InvestigationCase", "source_vertex_id": gid,
                                       "edge_type": etype, "target_vertex_type": ttype, "target_vertex_id": str(tid)})
        got = self.mcp.tool("get_node", {"vertex_type": "InvestigationCase", "vertex_id": gid})
        return gid if got.get("success", True) else ""
