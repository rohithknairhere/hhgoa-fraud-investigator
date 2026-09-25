import Image from "next/image";

import { CaseCard } from "@/components/CaseCard";
import { CaseLookupForm } from "@/components/CaseLookupForm";
import { Section } from "@/components/ui";
import { getAllCases } from "@/lib/server/data";

import heroImage from "@/public/images/graph-hero.png";

const LOOP = [
  ["Trigger", "A model score, a customer saying they didn't make a purchase, or an analyst asking a question."],
  ["Look at the graph", "Installed GSQL queries, called through the TigerGraph MCP server: the card's timeline, its devices, other cards on those devices, and the bank's closed cases."],
  ["Weigh it up", "A fraud probability from a model trained on the closed cases, adjusted by what the graph shows. The fraud policy decides what that number allows."],
  ["First recommendation", "Made before any extra evidence, with the approval each action needs. One weak signal means check with the customer first (R1)."],
  ["Ask if needed", "Customer validation or step-up authentication. The reply we assumed is written into the case."],
  ["Final recommendation", "Updated once the reply is in. A suspicious activity report is written only when the policy calls for one."],
  ["Explain", "The closest policy rules and past cases are pulled by vector search in TigerGraph and used to write the summary and any report."],
  ["Remember", "The case is saved back into TigerGraph, linked to its transactions, card, device and the closed cases it relied on."],
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
          <p className="eyebrow">HHGOA IEEE-CIS case pack</p>
          <h1 id="inbox-title" className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            Fraud cases
          </h1>
          <p className="max-w-xl text-base text-ink">
            Twenty alerts from November and December 2016, each investigated on TigerGraph. Open a case to see the
            evidence, what we recommended before and after asking the customer, and who has to sign off.
          </p>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Fraud", count("fraud")],
              ["Legitimate", count("legitimate")],
              ["Uncertain", count("uncertain")],
              ["Changed after asking", changed],
              ["Reports filed", sars],
              ["Saved in TigerGraph", inGraph],
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
            alt="Drawing of a transaction graph: one transaction in the middle linked to cards and devices, with the suspicious ones marked in red"
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

      <Section id="how-it-works" eyebrow="The process" title="How a case is worked">
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
