import type { WithPermittedActions } from '@/types/affordances';

/**
 * The single authorization primitive: may the caller perform `capability` on
 * `subject`? Tests membership in the subject's server-resolved
 * `permitted_actions`. A subject is anything carrying affordances — an object
 * (a comment) or the ambient scope (the active project).
 *
 * Pure and dependency-light (no React, no provider chain) so object-level
 * consumers can call it directly: `can(comment, Capability.Comment.UPDATE)`.
 * For ambient/scope checks use `useCan` from `@/components/common/Can`.
 *
 * Fail-closed: a null subject or missing `permitted_actions` yields false. The
 * backend is the single source of truth; this only does set membership.
 */
export function can(
  subject: WithPermittedActions | null | undefined,
  capability: string
): boolean {
  return subject?.permitted_actions?.includes(capability) ?? false;
}
