"""FastAPI runtime for the HHGOA investigation agent."""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.agent.planner import make_planner
from app.agent.policy import ACTIONS
from app.agent.service import investigate_scenario
from app.api.security import HTTPSEnforcementMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.config import Settings, get_settings
from app.data.scenarios import SCENARIOS, build_dataset
from app.graph.base import GraphProvider
from app.graph.factory import create_provider
from app.mcp_server.gateway import MCPToolGateway, open_gateway
from app.mcp_server.server import EVIDENCE_TOOLS

CASE_ID = Path(..., pattern=r"^HHGOA-\d{3}$")


class AnalystNote(BaseModel):
    author: str = Field(..., min_length=2, max_length=80)
    disposition: Literal["agree", "disagree", "needs_more_info"]
    note: str = Field(..., min_length=10, max_length=2000)

    @field_validator("author", "note")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if "<" in v or ">" in v:
            raise ValueError("angle brackets are not allowed")
        return v


class ExecuteRequest(BaseModel):
    action: str = Field(..., max_length=64)
    confirm: bool = True


class InvestigationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        build_dataset()
        self.scenarios = {s.case_id: s for s in SCENARIOS}
        self.provider: GraphProvider = create_provider(settings)
        self.planner = make_planner(settings.agent_planner, settings.anthropic_model)
        self.records: dict[str, dict[str, Any]] = {}
        self.executions: dict[str, dict[str, Any]] = {}
        self.notes: dict[str, list[dict[str, Any]]] = {}
        self.gateway: MCPToolGateway | None = None
        self._lock = asyncio.Lock()

    def load_cached(self) -> None:
        for sc in SCENARIOS:
            path = self.settings.benchmark_dir / f"{sc.case_id}.json"
            if path.exists():
                try:
                    self.records[sc.case_id] = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue

    async def investigate(self, case_id: str, force: bool = False) -> dict[str, Any]:
        async with self._lock:
            if case_id in self.records and not force:
                return self.records[case_id]
            assert self.gateway is not None
            record = await investigate_scenario(self.scenarios[case_id], self.gateway, self.planner,
                                                self.provider.name)
            self.records[case_id] = record
            return record


def summary(sc_id: str, svc: InvestigationService) -> dict[str, Any]:
    sc = svc.scenarios[sc_id]
    rec = svc.records.get(sc_id)
    out: dict[str, Any] = {
        "case_id": sc.case_id, "title": sc.title, "typology": sc.typology, "alert_rule": sc.alert_rule,
        "risk_score": sc.risk_score, "transaction_id": sc.focal_txn_id, "status": "open",
    }
    if rec:
        out.update({
            "status": "executed" if sc_id in svc.executions else "investigated",
            "initial_action": rec["nba_before_additional_evidence"]["action"],
            "final_action": rec["nba_after_additional_evidence"]["action"],
            "p_fraud": rec["final_decision"]["p_fraud"],
            "confidence": rec["final_decision"]["confidence"],
            "sar_required": rec["sar"]["required"],
        })
    return out


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    svc = InvestigationService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        svc.load_cached()
        async with open_gateway(svc.provider) as gateway:
            svc.gateway = gateway
            yield
        svc.gateway = None

    app = FastAPI(title="HHGOA Agentic Fraud Investigation API", version="1.0.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.service = svc

    # Order: outermost first → security headers wrap everything, HTTPS check before rate limiting.
    app.add_middleware(RateLimitMiddleware, read_per_minute=settings.rate_limit_per_minute,
                       write_per_minute=settings.rate_limit_write_per_minute)
    app.add_middleware(HTTPSEnforcementMiddleware, enabled=settings.enforce_https,
                       allow_local_http=settings.allow_local_http)
    app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.add_middleware(SecurityHeadersMiddleware)

    def require_case(case_id: str) -> None:
        if case_id not in svc.scenarios:
            raise HTTPException(404, f"case {case_id} not found")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "graph_backend": svc.provider.name, "planner": svc.planner.name,
                "cases_investigated": len(svc.records)}

    @app.get("/api/mcp/tools")
    async def mcp_tools() -> dict[str, Any]:
        assert svc.gateway is not None
        return {"server": "hhgoa-tigergraph", "tools": await svc.gateway.list_tools(evidence_only=True),
                "llm_allowlist": list(EVIDENCE_TOOLS)}

    @app.get("/api/cases")
    async def list_cases() -> dict[str, Any]:
        return {"cases": [summary(cid, svc) for cid in svc.scenarios]}

    @app.get("/api/cases/{case_id}")
    async def get_case(case_id: str = CASE_ID) -> dict[str, Any]:
        require_case(case_id)
        record = await svc.investigate(case_id)
        return {**record, "execution": svc.executions.get(case_id), "analyst_notes": svc.notes.get(case_id, [])}

    @app.post("/api/cases/{case_id}/investigate")
    async def reinvestigate(case_id: str = CASE_ID) -> dict[str, Any]:
        require_case(case_id)
        return await svc.investigate(case_id, force=True)

    @app.post("/api/cases/{case_id}/execute")
    async def execute(body: ExecuteRequest, case_id: str = CASE_ID) -> dict[str, Any]:
        require_case(case_id)
        record = await svc.investigate(case_id)
        recommended = record["nba_after_additional_evidence"]["action"]
        if body.action != recommended or body.action not in ACTIONS:
            raise HTTPException(409, f"action {body.action!r} does not match the recommended NBA {recommended!r}")
        if case_id in svc.executions:
            return {**svc.executions[case_id], "idempotent_replay": True}
        receipt = {
            "execution_id": f"EXE-{uuid.uuid4().hex[:10].upper()}",
            "case_id": case_id,
            "action": recommended,
            "label": ACTIONS[recommended]["label"],
            "executed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "executed (simulated)",
            "sar_submitted": record["sar"]["required"],
        }
        svc.executions[case_id] = receipt
        return receipt

    @app.post("/api/cases/{case_id}/notes", status_code=201)
    async def add_note(note: AnalystNote, case_id: str = CASE_ID) -> dict[str, Any]:
        require_case(case_id)
        entry = {**note.model_dump(), "id": uuid.uuid4().hex[:8],
                 "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        svc.notes.setdefault(case_id, []).append(entry)
        return entry

    @app.get("/api/patterns/device-sharing")
    async def device_sharing(min_cards: int = 3) -> dict[str, Any]:
        return {"devices": svc.provider.detect_device_sharing(max(2, min(min_cards, 50)))}

    @app.get("/api/patterns/velocity")
    async def velocity(window_seconds: int = 3600, min_txns: int = 6) -> dict[str, Any]:
        return {"bursts": svc.provider.detect_velocity_burst(max(60, min(window_seconds, 86_400)),
                                                             max(2, min(min_txns, 500)))}

    return app


app = create_app()
