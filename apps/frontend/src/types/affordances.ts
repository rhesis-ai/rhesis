/**
 * Server-driven authorization affordances.
 *
 * A resource carrying `permitted_actions` lists the full capability strings
 * (e.g. "comment:update", "comment:delete") the current caller may perform on
 * THAT specific object, resolved server-side — the same vocabulary as the
 * scope-level `GET /me/permissions` feed. The frontend renders affordances from
 * this list via `can` / `useCan` / `<Can>` and never re-derives `:own` or
 * ownership policy. Mix into any resource type that opts into the backend's
 * `WithPermittedActions` schema mixin.
 */
export interface WithPermittedActions {
  permitted_actions?: string[];
}
