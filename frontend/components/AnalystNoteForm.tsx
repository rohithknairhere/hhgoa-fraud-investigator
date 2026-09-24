"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { analystNoteSchema, type AnalystNoteInput } from "@/lib/schemas";

const DISPOSITIONS: { value: AnalystNoteInput["disposition"]; label: string }[] = [
  { value: "agree", label: "Agree with agent" },
  { value: "disagree", label: "Disagree" },
  { value: "needs_more_info", label: "Needs more info" },
];

export function AnalystNoteForm({ caseId }: { caseId: string }) {
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<AnalystNoteInput>({
    resolver: zodResolver(analystNoteSchema),
    mode: "onBlur",
    defaultValues: { author: "", note: "" },
  });

  async function onSubmit(values: AnalystNoteInput) {
    setResult(null);
    try {
      const res = await fetch(`/api/cases/${caseId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || body.detail?.[0]?.msg || "Could not save note");
      reset();
      setResult({
        ok: true,
        message: body.stored === false ? "Backend offline: note validated but not persisted." : "Note recorded on the case.",
      });
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Could not save note" });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4" aria-describedby="note-help">
      <p id="note-help" className="text-sm text-ink-muted">
        Record your review of the agent&apos;s decision. Notes are attached to the case audit trail.
      </p>
      <div>
        <label htmlFor="author" className="mb-1 block text-sm font-semibold text-ink">
          Analyst name
        </label>
        <input
          id="author"
          autoComplete="name"
          className="neu-input"
          aria-invalid={!!errors.author}
          aria-describedby={errors.author ? "author-error" : undefined}
          {...register("author")}
        />
        {errors.author && (
          <p id="author-error" className="mt-1 text-sm font-semibold text-danger">
            {errors.author.message}
          </p>
        )}
      </div>
      <fieldset>
        <legend className="mb-2 text-sm font-semibold text-ink">Disposition</legend>
        <div className="flex flex-wrap gap-3">
          {DISPOSITIONS.map((d) => (
            <label key={d.value} className="neu-sm flex cursor-pointer items-center gap-2 px-4 py-2 text-sm text-ink has-[:checked]:shadow-neu-inset">
              <input type="radio" value={d.value} className="accent-[#3730a3]" {...register("disposition")} />
              {d.label}
            </label>
          ))}
        </div>
        {errors.disposition && (
          <p className="mt-1 text-sm font-semibold text-danger" role="alert">
            {errors.disposition.message}
          </p>
        )}
      </fieldset>
      <div>
        <label htmlFor="note" className="mb-1 block text-sm font-semibold text-ink">
          Note
        </label>
        <textarea
          id="note"
          rows={4}
          className="neu-input resize-y"
          aria-invalid={!!errors.note}
          aria-describedby={errors.note ? "note-error" : undefined}
          {...register("note")}
        />
        {errors.note && (
          <p id="note-error" className="mt-1 text-sm font-semibold text-danger">
            {errors.note.message}
          </p>
        )}
      </div>
      <button type="submit" disabled={isSubmitting} className="neu-button focus-ring">
        {isSubmitting ? "Saving..." : "Save analyst note"}
      </button>
      <div aria-live="polite">
        {result && (
          <p className={`text-sm font-semibold ${result.ok ? "text-success" : "text-danger"}`}>{result.message}</p>
        )}
      </div>
    </form>
  );
}
