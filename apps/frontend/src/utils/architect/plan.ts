/**
 * Pure utilities for parsing and reasoning about architect plan markdown.
 *
 * Kept here (not inside a component) so both `PlanDisplay` and
 * `useArchitectChat` can import without creating a hook → component
 * dependency cycle.
 */

/**
 * Count actionable checklist items in a plan markdown string.
 *
 * Skips items tagged as *(existing)* or *(reuse)* — those were already
 * on the platform before this session and don't represent work the
 * agent still needs to do.
 */
/** Matches any `*(tag)*`-style status annotation on a checklist line. */
const STATUS_TAG_RE = /\*\([^)]+\)\*/;

export function countProgress(plan: string): { done: number; total: number } {
  const lines = plan.split('\n');
  let total = 0;
  let done = 0;
  for (const line of lines) {
    const trimmed = line.trimStart();
    if (!trimmed.startsWith('- [')) continue;
    // Skip items tagged with any *(…)* status annotation — these represent
    // already-existing entities and are not actionable work for this session.
    if (STATUS_TAG_RE.test(line)) continue;
    if (trimmed.startsWith('- [x]')) {
      total++;
      done++;
    } else if (trimmed.startsWith('- [ ]')) {
      total++;
    }
  }
  return { done, total };
}

/**
 * True when every actionable item in the plan markdown is checked off.
 *
 * A plan with no actionable items is **not** considered complete — it
 * means either the plan hasn't been generated yet or every item is
 * tagged as existing/reuse and there's nothing to track.
 */
export function isPlanComplete(plan: string): boolean {
  const { done, total } = countProgress(plan);
  return total > 0 && done === total;
}
