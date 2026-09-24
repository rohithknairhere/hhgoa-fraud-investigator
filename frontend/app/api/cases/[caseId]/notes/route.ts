import { NextResponse } from "next/server";

import { analystNoteSchema, caseIdSchema } from "@/lib/schemas";
import { backendFetch } from "@/lib/server/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request, { params }: { params: { caseId: string } }) {
  const id = caseIdSchema.safeParse(params.caseId);
  if (!id.success) return NextResponse.json({ error: "Invalid case id" }, { status: 400 });

  const parsed = analystNoteSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid note" }, { status: 422 });
  }

  const res = await backendFetch(`/api/cases/${id.data}/notes`, { method: "POST", body: JSON.stringify(parsed.data) });
  if (res) {
    const payload = await res.json().catch(() => ({ error: "Bad backend response" }));
    return NextResponse.json(payload, { status: res.status });
  }
  return NextResponse.json(
    { ...parsed.data, id: "offline", stored: false, note_status: "backend offline, note not persisted" },
    { status: 202 },
  );
}
