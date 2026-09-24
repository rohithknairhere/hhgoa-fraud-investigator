import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionTerminal } from "@/components/ActionTerminal";
import { AnalystNoteForm } from "@/components/AnalystNoteForm";
import { GraphPanel } from "@/components/GraphPanel";
import { ActionChip, Meter, Pill, Section } from "@/components/ui";
import { VERDICT_TONE, humanise, money } from "@/lib/actions";
import { caseGraph } from "@/lib/caseGraph";
import { getCase, listCaseIds } from "@/lib/server/data";

export const dynamicParams = false;

type Props = { params: { caseId: string } };

export async function generateStaticParams() {
  return (await listCaseIds()).map((caseId) => ({ caseId }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const v = await getCase(params.caseId);
  if (!v) return { title: "Case not found" };
  const c = v.answer.case;
  const description = `${humanise(v.pack.trigger_type)} on ${v.pack.card_id}. Verdict ${c.verdict}, pattern ${humanise(c.pattern)}, fraud probability ${c.fraud_probability.toFixed(2)}.`;
  return {
    title: `${v.pack.case_id}: ${c.verdict} (${humanise(c.pattern)})`,
    description,
    alternates: { canonical: `/cases/${v.pack.case_id}` },
    openGraph: { title: `${v.pack.case_id} investigation`, description, url: `/cases/${v.pack.case_id}`, type: "article" },
  };
}

const SOURCE_LABEL = { graph: "TigerGraph", document: "Policy / pattern text", customer: "Customer", external: "External" };

export default async function CasePage({ params }: Props) {
  const v = await getCase(params.caseId);
  if (!v) notFound();
  const { pack, answer } = v;
  const c = answer.case;
  const nba = answer.next_best_actions;
  const graph = caseGraph(v);
  const steps = [
    { title: "Trigger", body: pack.trigger_text },
    { title: "Investigate", body: `${answer.tool_calls} graph and retrieval calls through the TigerGraph MCP server; ${c.evidence.filter((e) => e.source === "graph").length} graph findings and ${c.similar_prior_cases.length} closed cases retrieved.` },
    { title: "Initial next best action", body: nba.initial.map((a) => `${a.action} (${a.route})`).join(", ") },
    ...answer.evidence_requests.map((r) => ({ title: `Evidence request: ${humanise(r.type)}`, body: `Assumed response: ${r.assumed_response}` })),
    { title: "Final next best action", body: `${nba.final.map((a) => `${a.action} (${a.route})`).join(", ")}. ${nba.what_changed === "nothing" ? "No change was needed." : nba.what_changed}` },
    { title: "Stop", body: answer.stop_reason },
    { title: "Case memory", body: c.written_to_graph ? `Written to TigerGraph as ${c.graph_case_id}, linked to its transactions, card, device and cited closed cases.` : "Not written to the graph." },
  ];

  return (
    <article className="space-y-8">
      <nav aria-label="Breadcrumb">
        <Link href="/" className="focus-ring neu-sm inline-flex px-4 py-2 text-sm font-semibold text-ink">
          Back to case inbox
        </Link>
      </nav>

      <header className="neu grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-3">
          <p className="eyebrow">
            {pack.case_id} | {humanise(pack.trigger_type)} | opened {pack.opened_at}
          </p>
          <h1 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">
            {c.pattern === "none" ? "No fraud found" : `${humanise(c.pattern).replace(/^./, (m) => m.toUpperCase())}`} on card {pack.card_id}
          </h1>
          <div className="flex flex-wrap gap-2">
            <Pill tone={VERDICT_TONE[c.verdict]}>{c.verdict}</Pill>
            <Pill tone="accent">{humanise(c.status)}</Pill>
            {answer.sar.file && <Pill tone="danger">SAR filed</Pill>}
            {c.written_to_graph && <Pill tone="success">In TigerGraph as {c.graph_case_id}</Pill>}
          </div>
          <p className="text-base text-ink">{c.summary}</p>
          <p className="font-mono text-xs text-ink-muted">
            flagged txn {pack.flagged_txn_id}, customer {pack.customer_id}, {answer.tool_calls} tool calls, {answer.tokens.toLocaleString()} LLM tokens, {answer.latency_s}s
          </p>
        </div>
        <div className="space-y-4">
          {pack.risk_score !== null && <Meter label="Bank risk score (input only)" value={pack.risk_score} tone="warning" />}
          <Meter label="Agent fraud probability" value={c.fraud_probability} tone="danger" />
          <div className="neu-inset rounded-2xl p-3 text-sm text-ink">
            Exposure <strong className="font-mono">{money(c.exposure_usd)}</strong> across {c.affected_txn_ids.length} transaction(s)
          </div>
        </div>
      </header>

      <Section id="action-terminal" eyebrow="Action terminal" title="Final next best actions">
        <ActionTerminal actions={nba.final} />
      </Section>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section id="progression" eyebrow="Case progression" title="How the case moved">
          <ol className="space-y-3">
            {steps.map((s, i) => (
              <li key={i} className="neu-sm flex gap-3 p-4">
                <span aria-hidden="true" className="neu-inset grid h-8 w-8 shrink-0 place-items-center rounded-xl font-mono text-sm font-bold text-accent">
                  {i + 1}
                </span>
                <div>
                  <p className="text-sm font-bold text-ink">{s.title}</p>
                  <p className="text-sm text-ink">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="nba" eyebrow="Uncertainty handling" title="Before and after more evidence">
          <p className="eyebrow mb-2">Initial</p>
          <ul className="mb-4 space-y-2">
            {nba.initial.map((a, i) => (
              <ActionChip key={i} a={a} showReason />
            ))}
          </ul>
          <p className="eyebrow mb-2">Final</p>
          <ul className="mb-4 space-y-2">
            {nba.final.map((a, i) => (
              <ActionChip key={i} a={a} showReason />
            ))}
          </ul>
          <p className="neu-inset rounded-2xl p-3 text-sm text-ink">
            <strong>What changed: </strong>
            {nba.what_changed}
          </p>
        </Section>
      </div>

      <Section id="graph-context" eyebrow="TigerGraph" title="Case sub-graph">
        <GraphPanel nodes={graph.nodes} edges={graph.edges} context={answer as unknown as Record<string, unknown>} />
      </Section>

      <Section id="evidence" eyebrow="Explainability" title="Evidence">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-separate border-spacing-y-2 text-left text-sm">
            <caption className="sr-only">Evidence used for the decision</caption>
            <thead>
              <tr className="text-xs uppercase tracking-wide text-ink-muted">
                <th scope="col" className="px-3">Claim</th>
                <th scope="col" className="px-3">Source</th>
                <th scope="col" className="px-3">Reference</th>
              </tr>
            </thead>
            <tbody>
              {c.evidence.map((e, i) => (
                <tr key={i} className="neu-sm align-top">
                  <td className="rounded-l-2xl px-3 py-3 text-ink">{e.claim}</td>
                  <td className="px-3 py-3 font-semibold text-ink">{SOURCE_LABEL[e.source] ?? e.source}</td>
                  <td className="rounded-r-2xl px-3 py-3 font-mono text-xs text-ink">{e.ref}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {c.pattern_description && (
          <p className="neu-inset mt-4 rounded-2xl p-4 text-sm text-ink">
            <strong>Undocumented pattern: </strong>
            {c.pattern_description}
          </p>
        )}
        <div className="mt-4 grid gap-3 sm:grid-cols-3 text-sm">
          <div className="neu-inset rounded-2xl p-3">
            <p className="eyebrow mb-1">Similar closed cases</p>
            <p className="font-mono text-xs text-ink">{c.similar_prior_cases.join(", ") || "none"}</p>
          </div>
          <div className="neu-inset rounded-2xl p-3">
            <p className="eyebrow mb-1">Connected cards</p>
            <p className="font-mono text-xs text-ink">{c.connected_card_ids.slice(0, 12).join(", ") || "none"}{c.connected_card_ids.length > 12 ? ` and ${c.connected_card_ids.length - 12} more` : ""}</p>
          </div>
          <div className="neu-inset rounded-2xl p-3">
            <p className="eyebrow mb-1">Affected transactions</p>
            <p className="font-mono text-xs text-ink">{c.affected_txn_ids.join(", ") || "none"}</p>
          </div>
        </div>
      </Section>

      <Section id="sar" eyebrow="Regulatory filing" title={answer.sar.file ? "Suspicious activity report" : "No report required"}>
        <p className="mb-3 text-sm text-ink">{answer.sar.reason}</p>
        {answer.sar.file && (
          <>
            <p className="neu-inset whitespace-pre-wrap rounded-2xl p-4 text-sm leading-7 text-ink">{answer.sar.narrative}</p>
            <p className="mt-3 font-mono text-xs text-ink-muted">
              Total {money(answer.sar.total_amount_usd)} | {answer.sar.activity_dates.join(" to ")} | subjects {answer.sar.subjects.join(", ")}
            </p>
          </>
        )}
      </Section>

      <Section id="analyst-notes" eyebrow="Human in the loop" title="Analyst review">
        <AnalystNoteForm caseId={pack.case_id} />
      </Section>
    </article>
  );
}
