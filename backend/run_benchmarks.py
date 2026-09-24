"""Run the 20 HHGOA benchmark cases and write one JSON record per case.

    python run_benchmarks.py [--out ../benchmark_results] [--planner deterministic|claude]

Exits non-zero if any case diverges from its expected outcome.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agent.planner import make_planner  # noqa: E402
from app.agent.service import investigate_scenario  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.data.scenarios import SCENARIOS, build_dataset  # noqa: E402
from app.graph.factory import create_provider  # noqa: E402
from app.graph.mock_provider import MockGraphProvider  # noqa: E402
from app.mcp_server.gateway import open_gateway  # noqa: E402


async def run(out_dir: Path, planner_kind: str) -> list[dict]:
    settings = get_settings()
    build_dataset()  # resolves focal transaction ids for the scenarios
    provider = create_provider(settings)
    planner = make_planner(planner_kind, settings.anthropic_model)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    async with open_gateway(provider) as gateway:
        for scenario in SCENARIOS:
            record = await investigate_scenario(scenario, gateway, planner, provider.name)
            (out_dir / f"{scenario.case_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            records.append(record)
            b = record["benchmark"]
            print(f"{'PASS' if b['passed'] else 'FAIL'} {scenario.case_id} "
                  f"initial={record['nba_before_additional_evidence']['action']:<42} "
                  f"final={record['nba_after_additional_evidence']['action']:<28} "
                  f"p={record['final_decision']['p_fraud']:.2f} conf={record['final_decision']['confidence']:.2f}")
    summary = {
        "graph_backend": provider.name,
        "planner": planner.name,
        "mock_fallback": isinstance(provider, MockGraphProvider),
        "total": len(records),
        "passed": sum(r["benchmark"]["passed"] for r in records),
        "initial_terminal": sum(r["nba_before_additional_evidence"]["terminal"] for r in records),
        "required_more_evidence": sum(r["additional_evidence_requested"] for r in records),
        "sar_filed": sum(r["sar"]["required"] for r in records),
        "cases": [{
            "case_id": r["case_id"], "title": r["title"], "typology": r["typology"],
            "risk_score": r["alert"]["risk_score"],
            "initial_action": r["nba_before_additional_evidence"]["action"],
            "final_action": r["nba_after_additional_evidence"]["action"],
            "p_fraud": r["final_decision"]["p_fraud"], "confidence": r["final_decision"]["confidence"],
            "evidence_rounds": len(r["investigation_record"]["nba_log"]) - 1,
            "sar_required": r["sar"]["required"], "passed": r["benchmark"]["passed"],
        } for r in records],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{summary['passed']}/{summary['total']} benchmark cases passed "
          f"(backend={summary['graph_backend']}, planner={summary['planner']})")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=get_settings().benchmark_dir)
    parser.add_argument("--planner", default=get_settings().agent_planner, choices=["deterministic", "claude"])
    args = parser.parse_args()
    records = asyncio.run(run(args.out, args.planner))
    return 0 if all(r["benchmark"]["passed"] for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
