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

const SOURCE_LABEL = { graph: "Graph", document: "Policy", customer: "Customer", external: "External" };

const HEADLINE: Record<string, string> = {
  none: "No fraud found",
  undocumented: "A pattern the bank hasn't documented",
  card_testing: "Card testing",
  card_not_present_fraud: "Card-not-present fraud",
  card_not_present_new_device: "Card-not-present fraud from a new device",
  out_of_region_use: "Use outside the home region",
  account_takeover: "Account takeover",
};

export default async function CasePage({ params }: Props) {
  const v = await getCase(params.caseId);
  if (!v) notFound();
  const { pack, answer } = v;
  const c = answer.case;
  const nba = answer.next_best_actions;
  const graph = caseGraph(v);
  const steps = [
    { title: "Alert", body: pack.trigger_text },
    { title: "Investigation", body: `${answer.tool_calls} graph and retrieval calls through the TigerGraph MCP server. ${c.evidence.filter((e) => e.source === "graph").length} findings from the graph, ${c.similar_prior_cases.length} closed cases pulled for comparison.` },
    { title: "First recommendation", body: nba.initial.map((a) => humanise(a.action).toLowerCase()).join(", ") },
    ...answer.evidence_requests.map((r) => ({ title: `Asked: ${humanise(r.type)}`, body: `Assumed reply: ${r.assumed_response}` })),
    { title: "Final recommendation", body: nba.final.map((a) => humanise(a.action).toLowerCase()).join(", ") },
    { title: "Closed out", body: answer.stop_reason },
    { title: "Saved to the graph", body: c.written_to_graph ? `Stored in TigerGraph as ${c.graph_case_id} for future cases to find.` : "Not saved to the graph." },
  ];

  return (
    <article className="space-y-8">
      <nav aria-label="Breadcrumb">
        <Link href="/" className="focus-ring neu-sm inline-flex px-4 py-2 text-sm font-semibold text-ink">
          Back to cases
        </Link>
      </nav>

      <header className="neu grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-3">
          <p className="eyebrow">
            {pack.case_id} | {humanise(pack.trigger_type)} | opened {pack.opened_at}
          </p>
          <h1 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">
            {HEADLINE[c.pattern] ?? humanise(c.pattern)} on card {pack.card_id}
          </h1>
          <div className="flex flex-wrap gap-2">
            <Pill tone={VERDICT_TONE[c.verdict]}>{c.verdict}</Pill>
            <Pill tone="accent">{humanise(c.status)}</Pill>
            {answer.sar.file && <Pill tone="danger">Report recommended</Pill>}
            {c.written_to_graph && <Pill tone="success">Saved as {c.graph_case_id}</Pill>}
          </div>
          <p className="text-base text-ink">{c.summary}</p>
          <p className="font-mono text-xs text-ink-muted">
            flagged txn {pack.flagged_txn_id}, customer {pack.customer_id}, {answer.tool_calls} tool calls, {answer.tokens.toLocaleString()} model tokens, {answer.latency_s}s
          </p>
        </div>
        <div className="space-y-4">
          {pack.risk_score !== null && <Meter label="Bank model score" value={pack.risk_score} tone="warning" />}
          <Meter label="Our fraud probability" value={c.fraud_probability} tone="danger" />
          <div className="neu-inset rounded-2xl p-3 text-sm text-ink">
            Exposure <strong className="font-mono">{money(c.exposure_usd)}</strong> across {c.affected_txn_ids.length} transaction(s)
          </div>
        </div>
      </header>

      <Section id="action-terminal" eyebrow="Next best action" title="What to do now">
        <ActionTerminal actions={nba.final} />
      </Section>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section id="progression" eyebrow="Timeline" title="How the case went">
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

        <Section id="nba" eyebrow="Uncertainty" title="Before and after asking">
          <p className="eyebrow mb-2">First</p>
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

      <Section id="graph-context" eyebrow="TigerGraph" title="Graph around this case">
        <GraphPanel nodes={graph.nodes} edges={graph.edges} context={answer as unknown as Record<string, unknown>} />
      </Section>

      <Section id="evidence" eyebrow="Why" title="Evidence">
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
            <strong>Pattern not in the bank&apos;s list: </strong>
            {c.pattern_description}
          </p>
        )}
        <div className="mt-4 grid gap-3 sm:grid-cols-3 text-sm">
          <div className="neu-inset rounded-2xl p-3">
            <p className="eyebrow mb-1">Closed cases used</p>
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

      <Section id="sar" eyebrow="Regulator" title={answer.sar.file ? "Suspicious activity report" : "No report needed"}>
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

      <Section id="analyst-notes" eyebrow="Review" title="Analyst note">
        <AnalystNoteForm caseId={pack.case_id} />
      </Section>
    </article>
  );
}
