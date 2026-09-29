import type { ContentType } from "./types";

// Fixed categorical order (validated palette) — colour follows the content type, never its rank.
export const TYPE_COLOR: Record<ContentType, string> = {
  lecture: "var(--cat-1)",
  previous_exam: "var(--cat-2)",
  assignment: "var(--cat-3)",
  answer_model: "var(--cat-4)",
  summary: "var(--cat-5)",
};
