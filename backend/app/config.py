"""Runtime configuration. All values come from the environment (or backend/.env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # TigerGraph
    tg_host: str = ""
    tg_graph: str = "HHGOA_IEEE"
    tg_username: str = ""
    tg_password: str = ""
    tg_secret: str = ""
    tg_connect_timeout_s: float = 3.0
    graph_backend: Literal["auto", "tigergraph", "mock"] = "auto"

    # Agent
    agent_planner: Literal["deterministic", "claude"] = "deterministic"
    anthropic_model: str = "claude-opus-5"
    confidence_threshold: float = 0.60
    max_evidence_rounds: int = 2

    # HTTP hardening
    enforce_https: bool = True
    allow_local_http: bool = True
    frontend_origin: str = "https://localhost:3000"
    rate_limit_per_minute: int = 120
    rate_limit_write_per_minute: int = 20

    benchmark_dir: Path = REPO_ROOT / "benchmark_results"


@lru_cache
def get_settings() -> Settings:
    return Settings()
