import Image from "next/image";

import { CaseCard } from "@/components/CaseCard";
import { CaseLookupForm } from "@/components/CaseLookupForm";
import { Section } from "@/components/ui";
import { getAllCases } from "@/lib/server/data";

import heroImage from "@/public/images/graph-hero.png";

const LOOP = [
  ["Trigger", "A risk-model score, a customer saying they never made a purchase, or an analyst request opens the investigation."],
  ["Investigate", "Installed GSQL queries on TigerGraph, called through the TigerGraph MCP server: the card timeline, device profiles, other cards on the same device, billing regions and closed cases."],
  ["Assess uncertainty", "A fraud probability from a classifier trained on the closed cases, moved by graph evidence. The policy decides what that probability allows."],
  ["Initial next best action", "Recommended with its approval route before any extra evidence. Weak signals mean verify first (R1)."],
  ["Gather more evidence", "Customer validation or step-up authentication. The assumed reply is recorded in the case file."],
  ["Final action and report", "The recommendation updates on the reply. A suspicious activity report is written only when the policy calls for one."],
  ["Explain", "Policy rules, pattern descriptions and closed-case narratives are retrieved by vector search in TigerGraph and given to Gemini to write the summary and report."],
  ["Case memory", "The case is written back to TigerGraph as an InvestigationCase vertex linked to its transactions, cards, devices and cited closed cases."],
];

export default async function InboxPage() {
  const cases = await getAllCases();
  const count = (v: string) => cases.filter((c) => c.answer.case.verdict === v).length;
  const changed = cases.filter((c) => c.answer.next_best_actions.what_changed !== "nothing").length;
  const sars = cases.filter((c) => c.answer.sar.file).length;
  const inGraph = cases.filter((c) => c.answer.case.written_to_graph).length;

  return (
    <div className="space-y-8">
      <section className="neu grid items-center gap-6 overflow-hidden p-6 sm:p-8 lg:grid-cols-[1.2fr_1fr]" aria-labelledby="inbox-title">
        <div className="space-y-4">
          <p className="eyebrow">Hacker House Goa | HHGOA IEEE-CIS case pack</p>
          <h1 id="inbox-title" className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            Case inbox
          </h1>
          <p className="max-w-xl text-base text-ink">
            The 20 benchmark cases, investigated on TigerGraph by our agent. Each one shows the evidence it found, what
            it recommended before and after asking for more information, who has to approve each action, and the
            report when the policy requires one.
          </p>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Fraud", count("fraud")],
              ["Legitimate", count("legitimate")],
              ["Uncertain", count("uncertain")],
              ["Changed after evidence", changed],
              ["SARs", sars],
              ["Written to TigerGraph", inGraph],
            ].map(([k, v]) => (
              <div key={k} className="neu-inset rounded-2xl p-3">
                <dt className="text-xs font-semibold text-ink-muted">{k}</dt>
                <dd className="font-mono text-2xl font-black text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="neu-inset rounded-3xl p-3">
          <Image
            src={heroImage}
            alt="Illustration of a transaction graph: a central transaction linked to cards, devices and regions, with suspicious nodes highlighted in red"
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
          <CaseCard key={c.pack.case_id} view={c} />
        ))}
      </ul>

      <Section id="how-it-works" eyebrow="Architecture" title="How the investigation works">
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {LOOP.map(([t, d], i) => (
            <li key={t} className="neu-sm p-4">
              <p className="font-mono text-xs font-bold text-accent">{String(i + 1).padStart(2, "0")}</p>
              <p className="font-bold text-ink">{t}</p>
              <p className="mt-1 text-sm text-ink">{d}</p>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}
