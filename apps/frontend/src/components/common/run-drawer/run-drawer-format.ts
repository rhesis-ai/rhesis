export const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? '' : 's'}`;

/** Joins the parts of a section's one-line summary, skipping empty ones. */
export const summaryOf = (...parts: (string | false | null | undefined)[]) =>
  parts.filter(Boolean).join(' · ');
