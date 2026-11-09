import type {
  RequirementReview,
  RequirementReviewHint,
  RequirementUpdate,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';

export type RuleHintId = 'no_source' | 'no_examples' | 'no_metric';

export interface RuleHint {
  id: RuleHintId;
  message: string;
}

export const RULE_HINT_MESSAGES: Record<RuleHintId, string> = {
  no_source: 'No source yet',
  no_examples: 'No examples yet',
  no_metric: 'No metric linked yet',
};

/** Gaps the page can spot on its own, without asking a model. */
export function ruleHints(
  requirement: Pick<
    RequirementWithMetrics,
    'sources' | 'examples_count' | 'metrics'
  >
): RuleHint[] {
  const ids: RuleHintId[] = [];
  if ((requirement.sources ?? []).length === 0) ids.push('no_source');
  if ((requirement.examples_count ?? 0) === 0) ids.push('no_examples');
  if ((requirement.metrics ?? []).length === 0) ids.push('no_metric');
  return ids.map(id => ({ id, message: RULE_HINT_MESSAGES[id] }));
}

/** The text a review hashes. Must match the backend byte for byte. */
export function reviewedText(name: string, description?: string | null) {
  return `${name}\n${description ?? ''}`;
}

/**
 * sha256 hex of the reviewed text, or null where Web Crypto is missing
 * (insecure origins), in which case a review is never shown as outdated.
 */
export async function requirementTextHash(
  name: string,
  description?: string | null
): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  const bytes = new TextEncoder().encode(reviewedText(name, description));
  const digest = await subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

/** A review is outdated once the name or description changed after it. */
export function isReviewOutdated(
  review: Pick<RequirementReview, 'description_hash'> | null | undefined,
  currentHash: string | null
): boolean {
  if (!review || currentHash === null) return false;
  return review.description_hash !== currentHash;
}

// Only these kinds carry a rewritten description. Older stored reviews can
// hold other kinds with a suggestion (e.g. a type name) that must not be applied.
const REWRITE_KINDS = new Set<string>(['vague_wording', 'unclear_behavior']);

/**
 * The description a hint's rewrite gives, or null when it has nothing to apply.
 * The rewrite replaces its quote, or the whole description when the quote is
 * not found.
 */
export function hintUpdate(
  hint: RequirementReviewHint,
  description: string | null | undefined
): RequirementUpdate | null {
  const suggestion = hint.suggestion?.trim();
  if (!suggestion || !REWRITE_KINDS.has(hint.kind)) return null;

  const current = description ?? '';
  if (hint.quote && current.includes(hint.quote)) {
    return { description: current.replace(hint.quote, suggestion) };
  }
  return { description: suggestion };
}

/** Stable key for a hint, for dismissing it and for React lists. */
export function hintKey(hint: RequirementReviewHint): string {
  return `${hint.kind}:${hint.quote ?? ''}:${hint.message}`;
}
