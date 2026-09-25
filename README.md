# HHGOA Agentic Fraud Investigator

An agent that investigates card fraud alerts on TigerGraph for the Hacker House Goa challenge. For each of the 20 cases in the HHGOA_IEEE case pack, it gathers evidence from the graph through the official TigerGraph MCP server and retrieves the fraud policy and similar closed cases by vector search. It decides under Fraud Policy v1.0 (rules R1 to R10) what to do before and after asking for more evidence, writes the case back into the graph, and produces an answer file in `cases/`.

## Submission contents

| What | Where |
|---|---|
| Answer files for the 20 cases | `cases/HHG-001.json` to `cases/HHG-020.json` |
| Monitoring beyond the 20 cases (optional, Innovation) | `monitoring/` |
| Case investigator (LangGraph workflow, policy engine) | `backend/hhgoa/agent.py` |
| TigerGraph access through `tigergraph-mcp` | `backend/hhgoa/tg_source.py` |
| GraphRAG explanation step (Gemini) | `backend/hhgoa/explain.py`, `backend/hhgoa/llm.py` |
| Knowledge base (policy, patterns, closed-case narratives with vectors) | `backend/hhgoa/knowledge.py` |
| Closed-case classifier | `backend/hhgoa/train_memory_model.py` |
| Autonomous monitoring | `backend/hhgoa/monitor.py` |
| Schema, loading job, investigation and monitoring queries | `tigergraph/hhgoa_ieee/` |
| Analyst dashboard (Next.js) | `frontend/` |
| Demo video | `demo/hhgoa_demo.mp4` |
| Blog post | `blog_post.md` |

## Architecture

```
case_pack.csv ──► LangGraph workflow ──────────────────────────────────────────────► cases/HHG-0XX.json
                   trigger, investigate, assess, initial action, evidence request,
                   final action, explain, write case memory
                        │                                  │
                        ▼                                  ▼
             tigergraph-mcp (stdio)                Gemini (Google AI Studio)
             allowlist: run_installed_query,       case summary, SAR narrative,
             add_node, add_edge, get_node          pattern description
                        │                                  ▲
                        ▼                                  │
             TigerGraph Savanna, graph HHGOA_IEEE ─────────┘
             590,742 transactions, 14,317 cards, 9,700 device profiles,
             5,565 closed cases, 417 knowledge chunks with 768-d vectors,
             one InvestigationCase vertex per investigated case
```

- **Graph.** Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion and ClosedCase, following the README's suggested schema. InvestigationCase stores our own cases, and KnowledgeChunk holds the policy, pattern and narrative text with a vector attribute.
- **Queries.** The agent calls installed queries only: `get_txn`, `card_window`, `device_neighbors`, `closed_cases_for_card`, `closed_cases_by_note`, `closed_cases_by_pattern`, `investigations_for_device` and `search_knowledge` (vector search). The MCP server is started with `TG_ALLOWED_TOOLS`, so the agent can't run arbitrary GSQL.
- **Graph algorithm.** `device_ring_components` runs weakly connected components over cards and proxied device profiles to find fraud rings across the whole exam period.
- **Policy engine.** It covers verify before blocking on a weak signal (R1), a customer denying a charge (R2), card testing (R5), shared origin (R6), disputes that match the customer's own habit (R7), escalation when uncertain (R8), undocumented patterns (R9), case versus report (3a), and the stopping rules (6). Approval routes are `auto`, `L1` or `L2`.
- **GraphRAG.** The case evidence is embedded with `gemini-embedding-001`. TigerGraph vector search returns the most relevant policy rules, pattern descriptions and closed-case narratives, and Gemini writes the summary and report from that context. Any ID the model writes that wasn't in its context is rejected, and the template text is kept instead.
- **Memory.** Closed cases are retrieved per alert. A LightGBM classifier trained only on the July to October closed cases gives a learned signal. Each finished case is written back as an InvestigationCase linked to its transactions, card, device, connected cards and cited closed cases. Later investigations query it, and cases are processed in the order they were opened, so memory never looks ahead.

## Reproduce

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt pandas pyarrow tigergraph-mcp
# put the HHGOA_IEEE files in ../dataset and fill backend/.env (TG_HOST, TG_SECRET, TG_GRAPH, GEMINI_API_KEY)
python -m hhgoa.prepare                     # CSV to Parquet
python hhgoa/train_memory_model.py          # closed-case classifier (needs lightgbm)
python -m hhgoa.tg schema                   # create the graph on TigerGraph
python -m hhgoa.tg load                     # load 590k transactions, closed cases and edges
python -m hhgoa.tg queries                  # install investigation queries
python -m hhgoa.knowledge build             # chunk and embed policy, patterns and narratives
python -m hhgoa.knowledge push              # load them into TigerGraph with vectors
python -m hhgoa.agent                       # investigate the 20 cases, write cases/ and the graph
python -m hhgoa.monitor                     # scan November and December, write monitoring/
cd ../frontend && npm install && npm run build && npm start
```

## Notes

- **Customer and analyst replies** aren't in the dataset. The reply the agent assumed is written in each case's `evidence_requests`, and its final actions follow from that assumption.
- **The LLM** writes explanations, not decisions. Verdicts and actions come from the graph evidence and the policy rules, so they're reproducible and auditable.
- **`backend/app/`** and **`benchmark_results/`** are the first prototype, built on a simulated graph before the dataset was available.
