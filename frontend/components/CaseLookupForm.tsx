"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { caseLookupSchema, type CaseLookupInput } from "@/lib/schemas";

export function CaseLookupForm() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CaseLookupInput>({ resolver: zodResolver(caseLookupSchema), defaultValues: { caseId: "" } });

  return (
    <form
      onSubmit={handleSubmit(({ caseId }) => router.push(`/cases/${caseId}`))}
      noValidate
      role="search"
      className="flex w-full flex-col gap-2 sm:w-auto"
    >
      <label htmlFor="caseId" className="text-sm font-semibold text-ink">
        Go to case
      </label>
      <div className="flex gap-2">
        <input
          id="caseId"
          placeholder="HHG-007"
          className="neu-input font-mono sm:w-44"
          aria-invalid={!!errors.caseId}
          aria-describedby={errors.caseId ? "caseId-error" : undefined}
          {...register("caseId")}
        />
        <button type="submit" className="neu-button focus-ring shrink-0">
          Open
        </button>
      </div>
      {errors.caseId && (
        <p id="caseId-error" className="text-sm font-semibold text-danger">
          {errors.caseId.message}
        </p>
      )}
    </form>
  );
}
