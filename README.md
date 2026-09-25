# HHGOA Fraud Desk

Our entry for the TigerGraph Hacker House Goa challenge. It's an agent that works card fraud alerts on TigerGraph: it pulls the evidence from the graph, decides whether that's enough to act on, asks the customer when it isn't, and recommends what the bank should do and who has to approve it. It follows the fraud policy in the dataset README (rules R1 to R10).

The answers for the 20 benchmark cases are in [`cases/`](cases), one JSON file per case.

## What's where

| Folder | Contents |
|---|---|
| `cases/` | Answer files for HHG-001 to HHG-020 |
| `monitoring/` | Extra alerts the agent raised on its own for November and December |
| `backend/hhgoa/` | The agent: data prep, TigerGraph loading, investigation workflow, write-ups, monitoring |
| `tigergraph/` | Schema, loading job, investigation queries and monitoring queries (GSQL) |
| `frontend/` | The analyst dashboard (Next.js) |
| `demo/` | Demo video |
| `blog_post.md` | Write-up of how we built it |

## How it works

All of the data lives in one graph on TigerGraph Savanna. Customers own cards, cards make transactions, and each transaction links to its device profile, email domain and billing region. The 5,565 closed cases link to the transactions and cards they covered. Two more vertex types hold what we add: `KnowledgeChunk` stores the fraud policy, the five pattern descriptions and the closed case notes with a 768-dimension vector each, and `InvestigationCase` stores every case the agent finishes.

For each alert, a LangGraph workflow runs these steps:

1. Read the alert: a model score, a customer report or an analyst request.
2. Query the graph through the official [TigerGraph MCP server](https://github.com/tigergraph/tigergraph-mcp). It is started with an allowlist of four tools (run an installed query, add a node, add an edge, read a node), so the agent can't send its own GSQL.
3. Work out a fraud probability. It starts from a LightGBM model trained only on the July to October closed cases, and moves with what the graph shows: new devices, unusual amounts, unfamiliar regions, other cards on the same device, and our own earlier cases.
4. Recommend a first set of actions under the policy, each with its approval route (`auto`, `L1` or `L2`).
5. Ask the customer if the policy says to. Replies aren't in the dataset, so the reply we assumed is written into `evidence_requests`.
6. Recommend the final actions, and write a suspicious activity report when the policy calls for one.
7. Pull the most relevant policy rules and past cases with TigerGraph vector search, and have Gemini write the summary and the report from them. If the model mentions an ID it wasn't given, its text is dropped and a template is used instead.
8. Save the case back into TigerGraph, linked to its transactions, card, device and the closed cases it used. Cases run in the order they were opened, so none of them can see a later one.

The decisions come from the graph evidence and the policy rules, not from the language model, so the same data always gives the same answer.

On top of the 20 cases, `hhgoa.monitor` scans November and December for trouble nobody reported. A connected components query over cards and proxied device profiles finds a 28-card ring built around a single phone, and a second query finds cards hit by bursts of purchases just under $500.

## Running it

You need the HHGOA_IEEE files in `dataset/`, a TigerGraph Savanna workspace, and a Google AI Studio key in `backend/.env` (see `backend/.env.example`).

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

python -m hhgoa.prepare # CSV to Parquet
python hhgoa/train_memory_model.py # model trained on the closed cases
python -m hhgoa.tg schema # create the graph
python -m hhgoa.tg load # load transactions, cards, devices, closed cases
python -m hhgoa.tg queries # install the investigation queries
python -m hhgoa.knowledge build # embed the policy, patterns and case notes
python -m hhgoa.knowledge push # load them into TigerGraph
python -m hhgoa.agent # work the 20 cases, write cases/ and the graph
python -m hhgoa.monitor # scan November and December, write monitoring/
```

The dashboard reads the files in `cases/`:

```bash
cd frontend
npm install
npm run build
npm start
```
