/**
 * Returns true when a freshly computed graph should be treated as complete
 * relative to a baseline timestamp captured before enqueueing recompute.
 */
export function isEmbeddingGraphNewerThanBaseline(
  computedAt: string,
  baselineComputedAt: string | null
): boolean {
  if (baselineComputedAt === null) {
    return true;
  }
  return (
    new Date(computedAt).getTime() > new Date(baselineComputedAt).getTime()
  );
}
