import { NextResponse } from "next/server";

import { analystNoteSchema, caseIdSchema } from "@/lib/schemas";

export const dynamic = "force-dynamic";

// Validates an analyst note server-side. Notes are acknowledged but not persisted in this demo.
export async function POST(request: Request, { params }: { params: { caseId: string } }) {
  const id = caseIdSchema.safeParse(params.caseId);
  if (!id.success) return NextResponse.json({ error: "Invalid case id" }, { status: 400 });
  const parsed = analystNoteSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid note" }, { status: 422 });
  }
  return NextResponse.json({ ...parsed.data, case_id: id.data, stored: false }, { status: 202 });
}
