import Image from "next/image";

import { CaseCard } from "@/components/CaseCard";
import { CaseLookupForm } from "@/components/CaseLookupForm";
import { Section } from "@/components/ui";
import { getCaseSummaries } from "@/lib/server/data";

import heroImage from "@/public/images/graph-hero.png";

export const revalidate = 60;

const LOOP = [
  ["Trigger", "A risk-engine alert (rule + score) opens the case."],
  ["Investigate", "GraphRAG: typed TigerGraph MCP tools fetch the transaction sub-graph and similar closed cases."],
  ["Assess uncertainty", "Each graph finding shifts the fraud probability. Confidence also accounts for missing checks and conflicting signals."],
  ["Next best action", "At 0.60 confidence or higher the agent blocks, allows or files a SAR. Below that it logs an interim action such as step-up auth."],
  ["Gather more evidence", "Customer step-up or analyst findings arrive; the loop re-assesses (max two rounds)."],
  ["Update case memory", "Decision, evidence ids and outcome are written back to the Case vertex for future retrieval."],
];

export default async function InboxPage() {
  const { cases, source } = await getCaseSummaries();
  const moreEvidence = cases.filter((c) => c.initial_action && c.initial_action !== c.final_action).length;
  const sar = cases.filter((c) => c.sar_required).length;
  const blocked = cases.filter((c) => c.final_action?.startsWith("BLOCK")).length;

  return (
    <div className="space-y-8">
      <section className="neu grid items-center gap-6 overflow-hidden p-6 sm:p-8 lg:grid-cols-[1.2fr_1fr]" aria-labelledby="inbox-title">
        <div className="space-y-4">
          <p className="eyebrow">Hacker House Goa | IEEE-CIS benchmark</p>
          <h1 id="inbox-title" className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            Case inbox
          </h1>
          <p className="max-w-xl text-base text-ink">
            Twenty simulated alerts investigated by a LangGraph agent that gathers evidence only through TigerGraph MCP
            tools, measures its own uncertainty, and logs its next-best action before and after asking for more evidence.
          </p>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Cases", cases.length],
              ["Needed more evidence", moreEvidence],
              ["Blocked", blocked],
              ["SARs filed", sar],
            ].map(([k, v]) => (
              <div key={k} className="neu-inset rounded-2xl p-3">
                <dt className="text-xs font-semibold text-ink-muted">{k}</dt>
                <dd className="font-mono text-2xl font-black text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-ink-muted">
            Data source: {source === "live" ? "live FastAPI backend" : "benchmark snapshot (backend offline)"}
          </p>
        </div>
        <div className="neu-inset rounded-3xl p-3">
          <Image
            src={heroImage}
            alt="Illustration of a transaction graph: a central transaction linked to cards, devices and IPs, with suspicious nodes highlighted in red"
            priority
            placeholder="blur"
            sizes="(min-width: 1024px) 40vw, 100vw"
            className="h-auto w-full rounded-2xl"
          />
        </div>
      </section>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <h2 className="text-xl font-bold text-ink">All cases</h2>
        <CaseLookupForm />
      </div>

      <ul className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3" aria-label="Benchmark cases">
        {cases.map((c) => (
          <CaseCard key={c.case_id} c={c} />
        ))}
      </ul>

      <Section id="how-it-works" eyebrow="Architecture" title="How the investigation loop works">
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {LOOP.map(([t, d], i) => (
            <li key={t} className="neu-sm p-4">
              <p className="font-mono text-xs font-bold text-accent">0{i + 1}</p>
              <p className="font-bold text-ink">{t}</p>
              <p className="mt-1 text-sm text-ink">{d}</p>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}
