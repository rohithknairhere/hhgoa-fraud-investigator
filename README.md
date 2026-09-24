# HHGOA Agentic Fraud Investigator

This is an agentic fraud investigation system for the TigerGraph Hacker House Goa challenge. It investigates the 20 cases in the HHGOA_IEEE case pack. For each case it gathers evidence from the transaction graph and the bank's closed cases, estimates its own uncertainty, and follows Fraud Policy v1.0 (rules R1–R10) to recommend next best actions with approval routes. It writes one answer file per case to `cases/`.

## Submission contents

| What | Where |
|---|---|
| Answer files for the 20 cases (README answer format) | `cases/HHG-001.json` … `cases/HHG-020.json` |
| Case investigator (LangGraph workflow, policy engine, SAR writer) | `backend/hhgoa/agent.py` |
| Data preparation (CSV → Parquet graph mirror) | `backend/hhgoa/prepare.py` |
| Closed-case memory classifier | `backend/hhgoa/train_memory_model.py` |
| TigerGraph schema and investigation queries for the real dataset | `tigergraph/hhgoa_ieee/` |
| MCP server exposing typed graph tools | `backend/app/mcp_server/` |
| Analyst dashboard (Next.js) | `frontend/` |
| Demo video | `demo/hhgoa_demo.mp4` |
| Blog post | `blog_post.md` |

## Reproduce the answer files

```bash
cd backend
python -m hhgoa.prepare                    # needs dataset/*.csv from the HHGOA_IEEE folder
python hhgoa/train_memory_model.py         # needs lightgbm
python -m hhgoa.agent                      # writes ../cases/*.json
```

## How the agent works

1. **Trigger.** A case from `case_pack.csv`: a risk score, a customer report, or an analyst request.
2. **Investigate.** Named graph queries run on the card: `card_window`, `card_history`, `region_history`, `device_neighbors` and `similar_closed_cases`. They cover the card's timeline, its device profiles (DeviceInfo + OS + browser + screen), the other cards sharing a profile, billing-region history, and matching closed cases.
3. **Assess.** The agent detects the five documented patterns and two undocumented ones found in the closed-case notes: a just-under-$500 online burst, and a shared device ring behind an anonymous proxy. It then estimates fraud probability, the fraud episode, exposure and connected cards.
4. **Initial next best action.** Recommended under R1/R5/R7/R9, with `auto`/`L1`/`L2` routes. A case is opened whenever evidence is requested (policy 3a).
5. **Gather more evidence.** Customer validation or step-up auth. Responses are simulated and recorded in `evidence_requests`, as the README instructs.
6. **Final next best action.** Recommended under R2/R3/R4/R6/R8/R9. A SAR narrative is written when `FILE_REPORT` is recommended.
7. **Stop.** Follows the policy 6 stopping rules; the reason is recorded in `stop_reason`.
8. **Case memory.** The closed cases are retrieved and cited in `similar_prior_cases`. A LightGBM classifier trained only on the Jul–Oct closed cases, using Vesta's unnamed V/C/D/M features, provides a learned signal. The evidence cites it as such.

## Honest status

- **TigerGraph:** no live instance was available during the build (no Savanna credentials or Docker on the build machine). The agent ran on a local Parquet mirror with the same vertex and edge semantics, and cites the GSQL query it would call. `written_to_graph` is therefore `false` in every answer file. To load TigerGraph, run `tigergraph/hhgoa_ieee/schema.gsql` and `queries.gsql`, load the CSVs, set `TG_*` in `backend/.env`, and rerun.
- **LLM:** no API key was configured, so summaries and SAR narratives come from templates filled from the evidence, and `tokens` is 0. The Claude planner in `backend/app/agent/planner.py` activates when `ANTHROPIC_API_KEY` is set.
- **Simulated responses:** customer and analyst replies are not provided by the dataset. The assumption made for each case is stated in `evidence_requests`.

## Earlier prototype

`backend/app/` (FastAPI, MCP server and gateway, LangGraph loop), `frontend/` and `benchmark_results/` are the first prototype, built on a simulated graph before the real dataset was available. See `run.sh` to start that stack.
