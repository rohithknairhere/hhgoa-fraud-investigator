"""GraphRAG knowledge base: fraud policy rules, known patterns, investigation guidance and closed-case
narratives, embedded with Gemini and stored as KnowledgeChunk vertices with a vector attribute in TigerGraph.

    python -m hhgoa.knowledge build     chunk + embed (.store/knowledge.parquet)
    python -m hhgoa.knowledge push      create KnowledgeChunk type and load chunks + vectors into TigerGraph
"""

from __future__ import annotations

import re
import sys

import pandas as pd

from hhgoa.paths import DATASET, STORE

KB = STORE / "knowledge.parquet"


def readme_chunks() -> list[dict]:
    text = (DATASET / "README.md").read_text(encoding="utf-8")
    chunks: list[dict] = []

    def section(title: str, stop: str) -> str:
        a = text.index(title)
        b = text.index(stop, a + len(title))
        return text[a:b]

    pats = section("## The five known fraud patterns", "## Regulatory references")
    for m in re.finditer(r"\*\*(\d)\. ([^*]+)\*\*(.+?)(?=\n\n\*\*\d\.|\Z)", pats, re.S):
        chunks.append({"source": "patterns", "section": f"Pattern {m.group(1)}: {m.group(2).strip('. ')}",
                       "text": f"{m.group(2)} {m.group(3).strip()}"})
    rules = section("### 3. Rules", "### 3a.")
    for m in re.finditer(r"\*\*(R\d+)\. ([^*]+)\*\*(.+?)(?=\n\n\*\*R\d+|\Z)", rules, re.S):
        chunks.append({"source": "policy", "section": m.group(1), "text": f"{m.group(1)}. {m.group(2)} {m.group(3).strip()}"})
    for title, stop in [("### 1. Actions", "### 2."), ("### 2. Approval routing", "### 3. Rules"),
                        ("### 3a. A case is not a report", "### 3b."), ("### 3b. The next best action can change", "### 4."),
                        ("### 4. Exposure", "### 5."), ("### 5. Gathering more evidence", "### 6."),
                        ("### 6. Stopping", "### 7."), ("### 7. Explaining", "---"),
                        ("## Things to know", "## Rules"), ("### 0. What the agent starts with", "### 1.")]:
        chunks.append({"source": "policy", "section": title.strip("# "), "text": section(title, stop).strip()})
    return chunks


def narrative_chunks() -> list[dict]:
    cc = pd.read_parquet(STORE / "closed_cases.parquet")
    # Many notes share a template; keep one representative per template (IDs, amounts and dates normalised).
    norm = (cc.analyst_notes.str.replace(r"CC-\d+", "CC", regex=True).str.replace(r"C\d{5}(-K\d)?", "CUST", regex=True)
            .str.replace(r"\$[\d,.]+", "$X", regex=True).str.replace(r"\d{4}-\d{2}-\d{2}", "DATE", regex=True)
            .str.replace(r"\b\d+(\.\d+)?\b", "N", regex=True))
    cc = cc.assign(norm=norm)
    reps = cc.groupby("norm").agg(case_id=("case_id", "first"), n=("case_id", "size"), pattern=("pattern", "first"),
                                  outcome=("outcome", "first"), text=("analyst_notes", "first")).reset_index(drop=True)
    return [{"source": "closed_case", "section": f"{r.case_id} ({r.outcome}, {r.pattern}, {r.n} similar notes)", "text": r.text}
            for r in reps.itertuples()]


def build() -> None:
    from hhgoa.llm import Gemini

    chunks = readme_chunks() + narrative_chunks()
    df = pd.DataFrame(chunks)
    df.insert(0, "chunk_id", [f"KC-{i:04d}" for i in range(len(df))])
    df["embedding"] = Gemini().embed([f"{s}: {t}" for s, t in zip(df.section, df.text)])
    df.to_parquet(KB, index=False)
    print(df.source.value_counts().to_dict(), "chunks embedded")


SCHEMA = """
USE GRAPH HHGOA_IEEE
CREATE SCHEMA_CHANGE JOB add_kc_local FOR GRAPH HHGOA_IEEE {
  ADD VERTEX KnowledgeChunk (PRIMARY_ID chunk_id STRING, source STRING, section STRING, text STRING) WITH primary_id_as_attribute="true";
}
RUN SCHEMA_CHANGE JOB add_kc_local
CREATE SCHEMA_CHANGE JOB add_kc_vec FOR GRAPH HHGOA_IEEE {
  ALTER VERTEX KnowledgeChunk ADD VECTOR ATTRIBUTE embedding(DIMENSION=768, METRIC="COSINE");
}
RUN SCHEMA_CHANGE JOB add_kc_vec
"""

JOB = """
USE GRAPH HHGOA_IEEE
CREATE LOADING JOB load_knowledge FOR GRAPH HHGOA_IEEE {
  DEFINE FILENAME f_kc;
  LOAD f_kc TO VERTEX KnowledgeChunk VALUES ($0, $1, $2, $3) USING header="true", separator="|", quote="double";
  LOAD f_kc TO VECTOR ATTRIBUTE embedding ON VERTEX KnowledgeChunk VALUES ($0, SPLIT($4, ":")) USING header="true", separator="|", quote="double";
}
"""

QUERY = """
USE GRAPH HHGOA_IEEE
CREATE OR REPLACE QUERY search_knowledge(LIST<FLOAT> qv, SET<STRING> sources, INT k = 6) FOR GRAPH HHGOA_IEEE SYNTAX v3 {
  MapAccum<VERTEX, FLOAT> @@dist;
  All = {KnowledgeChunk.*};
  Cand = SELECT c FROM All:c WHERE sources.size() == 0 OR sources.contains(c.source);
  R = vectorSearch({KnowledgeChunk.embedding}, qv, k, {candidate_set: Cand, distance_map: @@dist});
  PRINT R[R.chunk_id, R.source, R.section, R.text] AS chunks;
  PRINT @@dist AS distances;
}
INSTALL QUERY search_knowledge
"""


def push() -> None:
    from hhgoa.tg import connect

    df = pd.read_parquet(KB)
    conn = connect()
    if "KnowledgeChunk" not in conn.gsql("USE GRAPH HHGOA_IEEE\nls"):
        print(conn.gsql(SCHEMA)[-600:])
    print(conn.gsql(JOB)[-300:])
    out = STORE / "tg_export" / "knowledge.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    flat = df.assign(text=df.text.str.replace("|", "/", regex=False).str.replace("\n", " ", regex=False),
                     section=df.section.str.replace("|", "/", regex=False),
                     embedding=df.embedding.map(lambda v: ":".join(f"{x:.6f}" for x in v)))
    flat[["chunk_id", "source", "section", "text", "embedding"]].to_csv(out, index=False, sep="|")
    print(str(conn.runLoadingJobWithFile(str(out), "f_kc", "load_knowledge", sep="|"))[:300])
    print(conn.gsql(QUERY)[-600:])


if __name__ == "__main__":
    {"build": build, "push": push}[sys.argv[1]]()
