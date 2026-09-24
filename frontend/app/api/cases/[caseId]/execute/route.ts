import { NextResponse } from "next/server";

import { caseIdSchema, executeSchema } from "@/lib/schemas";
import { backendFetch, getCase } from "@/lib/server/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request, { params }: { params: { caseId: string } }) {
  const id = caseIdSchema.safeParse(params.caseId);
  if (!id.success) return NextResponse.json({ error: "Invalid case id" }, { status: 400 });

  const body = executeSchema.safeParse(await request.json().catch(() => null));
  if (!body.success) return NextResponse.json({ error: "Invalid action" }, { status: 422 });

  // Proxy server-side so the backend URL never reaches the browser.
  const res = await backendFetch(`/api/cases/${id.data}/execute`, {
    method: "POST",
    body: JSON.stringify({ action: body.data.action, confirm: true }),
  });
  if (res) {
    const payload = await res.json().catch(() => ({ error: "Bad backend response" }));
    return NextResponse.json(payload, { status: res.status });
  }

  // Backend offline: validate against the snapshot and return a clearly-labelled simulated receipt.
  const found = await getCase(id.data);
  if (!found) return NextResponse.json({ error: "Case not found" }, { status: 404 });
  const recommended = found.record.nba_after_additional_evidence;
  if (recommended.action !== body.data.action) {
    return NextResponse.json({ error: `Action does not match recommended NBA ${recommended.action}` }, { status: 409 });
  }
  return NextResponse.json({
    execution_id: `SIM-${id.data}-${Date.now().toString(36).toUpperCase()}`,
    case_id: id.data,
    action: recommended.action,
    label: recommended.label,
    executed_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
    status: "simulated (backend offline)",
    sar_submitted: found.record.sar.required,
  });
}
