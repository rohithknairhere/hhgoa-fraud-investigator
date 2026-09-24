import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionTerminal } from "@/components/ActionTerminal";
import { AnalystNoteForm } from "@/components/AnalystNoteForm";
import { GraphPanel } from "@/components/GraphPanel";
import { ActionBadge, Meter, Section } from "@/components/ui";
import { Waterfall } from "@/components/Waterfall";
import { humanise, pct } from "@/lib/actions";
import { getCase, listCaseIds } from "@/lib/server/data";

export const revalidate = 60;
export const dynamicParams = false;

type Props = { params: { caseId: string } };

export async function generateStaticParams() {
  return (await listCaseIds()).map((caseId) => ({ caseId }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const found = await getCase(params.caseId);
  if (!found) return { title: "Case not found" };
  const r = found.record;
  const description = `${r.title}. Initial NBA: ${r.nba_before_additional_evidence.label}; final: ${r.nba_after_additional_evidence.label} (p(fraud) ${pct(r.final_decision.p_fraud)}).`;
  return {
    title: `${r.case_id}: ${r.title}`,
    description,
    alternates: { canonical: `/cases/${r.case_id}` },
    openGraph: { title: `${r.case_id}: ${r.title}`, description, url: `/cases/${r.case_id}`, type: "article" },
    twitter: { card: "summary_large_image", title: `${r.case_id}: ${r.title}`, description },
  };
}

export default async function CasePage({ params }: Props) {
  const found = await getCase(params.caseId);
  if (!found) notFound();
  const { record: r, source } = found;
  const ir = r.investigation_record;
  const evidenceById = new Map(ir.evidence.map((e) => [e.evidence_id, e]));
  const before = r.nba_before_additional_evidence;
  const after = r.nba_after_additional_evidence;

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
            {r.case_id} | {humanise(r.typology)} | alert {r.alert.rule}
          </p>
          <h1 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">{r.title}</h1>
          <p className="font-mono text-sm text-ink">
            txn {ir.transaction_id}, customer {ir.customer_id}, tags {ir.pattern_tags.join(", ") || "none"}
          </p>
          <p className="text-xs text-ink-muted">
            Graph backend <strong className="text-ink">{r.graph_backend}</strong>, planner{" "}
            <strong className="text-ink">{r.planner}</strong>, {ir.mcp_tool_calls.length} MCP calls,{" "}
            {source === "live" ? "live" : "snapshot"} data
          </p>
        </div>
        <div className="space-y-4">
          <Meter label="Alert risk score" value={r.alert.risk_score} tone="warning" />
          <Meter label="p(fraud) after investigation" value={r.final_decision.p_fraud} tone="danger" />
          <Meter label="Decision confidence" value={r.final_decision.confidence} tone="accent" />
        </div>
      </header>

      <Section id="action-terminal" eyebrow="Action terminal" title="Next best action">
        <ActionTerminal
          caseId={r.case_id}
          action={after.action}
          rationale={after.rationale}
          sarRequired={r.sar.required}
        />
      </Section>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section id="nba-log" eyebrow="Uncertainty handling" title="NBA before vs after more evidence">
          <ol className="space-y-4">
            {ir.nba_log.map((n, i) => (
              <li key={i} className="neu-sm space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="eyebrow">
                    {n.phase === "initial" ? "Initial NBA" : `Updated NBA (round ${n.round})`}
                  </span>
                  <ActionBadge action={n.action} />
                </div>
                <p className="text-sm text-ink">{n.rationale}</p>
                <p className="font-mono text-xs text-ink-muted">
                  p(fraud) {n.p_fraud.toFixed(2)}, confidence {n.confidence.toFixed(2)}, drivers:{" "}
                  {n.key_drivers.join(", ")}
                </p>
              </li>
            ))}
          </ol>
          {r.additional_evidence.length > 0 ? (
            <div className="mt-4">
              <p className="eyebrow mb-2">Additional evidence received</p>
              <ul className="space-y-2">
                {r.additional_evidence.map((e) => (
                  <li key={e.evidence_id} className="neu-inset rounded-2xl p-3 text-sm text-ink">
                    <span className="font-mono font-bold">{e.evidence_id}</span> ({humanise(e.source)}):{" "}
                    {e.description}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-4 text-sm text-ink-muted">
              Confidence cleared the 0.60 threshold on the first pass, so no additional evidence was requested (before
              = after: <strong className="text-ink">{before.label}</strong>).
            </p>
          )}
        </Section>

        <Section id="waterfall" eyebrow="LangGraph trace" title="Investigation waterfall">
          <Waterfall steps={ir.trace} />
        </Section>
      </div>

      <Section id="graph-context" eyebrow="TigerGraph" title="Graph context">
        <GraphPanel nodes={ir.graph_context.view.nodes} edges={ir.graph_context.view.edges} context={ir.graph_context} />
      </Section>

      <Section id="explainability" eyebrow="Explainability" title="Evidence behind the decision">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-separate border-spacing-y-2 text-left text-sm">
            <caption className="sr-only">Signals and the TigerGraph evidence that supports each</caption>
            <thead>
              <tr className="text-xs uppercase tracking-wide text-ink-muted">
                <th scope="col" className="px-3">Signal</th>
                <th scope="col" className="px-3">Log-odds</th>
                <th scope="col" className="px-3">Finding</th>
                <th scope="col" className="px-3">Evidence (MCP tool)</th>
              </tr>
            </thead>
            <tbody>
              {r.final_decision.justification.map((s) => (
                <tr key={s.name} className="neu-sm align-top">
                  <td className="rounded-l-2xl px-3 py-3 font-semibold text-ink">{humanise(s.name)}</td>
                  <td className={`px-3 py-3 font-mono font-bold ${s.contribution > 0 ? "text-danger" : "text-success"}`}>
                    {s.contribution > 0 ? "+" : ""}
                    {s.contribution.toFixed(2)}
                  </td>
                  <td className="px-3 py-3 text-ink">{s.description}</td>
                  <td className="rounded-r-2xl px-3 py-3 font-mono text-xs text-ink">
                    {s.evidence_ids.map((id) => {
                      const e = evidenceById.get(id);
                      return (
                        <span key={id} className="block">
                          {id}: {e?.tool ?? e?.source ?? "n/a"}
                        </span>
                      );
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {r.sar.required && r.sar.narrative && (
        <Section id="sar" eyebrow={r.sar.filing_type} title="Suspicious Activity Report narrative">
          <pre className="neu-inset whitespace-pre-wrap rounded-2xl p-4 font-mono text-xs leading-6 text-ink">
            {r.sar.narrative}
          </pre>
        </Section>
      )}

      <Section id="analyst-notes" eyebrow="Human in the loop" title="Analyst review">
        <AnalystNoteForm caseId={r.case_id} />
      </Section>
    </article>
  );
}
