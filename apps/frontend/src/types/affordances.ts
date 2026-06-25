/**
 * Server-driven authorization affordances.
 *
 * A resource carrying `permitted_actions` lists the action names (capability
 * middle-segment, e.g. "update", "delete", "react") the current caller may
 * perform on THAT specific object, resolved server-side. The frontend renders
 * affordances from this list via `useCan` / `<Can>` and never re-derives `:own`
 * or ownership policy. Mix into any resource type that opts into the backend's
 * `WithPermittedActions` schema mixin.
 */
export interface WithPermittedActions {
  permitted_actions?: string[];
}
