import { z } from "zod";

import { CASE_ID_PATTERN } from "./actions";

const noMarkup = (v: string) => !/[<>]/.test(v);

export const caseIdSchema = z
  .string()
  .trim()
  .toUpperCase()
  .regex(CASE_ID_PATTERN, "Use the format HHG-001");

export const caseLookupSchema = z.object({ caseId: caseIdSchema });
export type CaseLookupInput = z.infer<typeof caseLookupSchema>;

export const analystNoteSchema = z.object({
  author: z
    .string()
    .trim()
    .min(2, "Name must be at least 2 characters")
    .max(80, "Name must be at most 80 characters")
    .refine(noMarkup, "Angle brackets are not allowed"),
  disposition: z.enum(["agree", "disagree", "needs_more_info"], {
    errorMap: () => ({ message: "Choose a disposition" }),
  }),
  note: z
    .string()
    .trim()
    .min(10, "Note must be at least 10 characters")
    .max(2000, "Note must be at most 2000 characters")
    .refine(noMarkup, "Angle brackets are not allowed"),
});
export type AnalystNoteInput = z.infer<typeof analystNoteSchema>;
