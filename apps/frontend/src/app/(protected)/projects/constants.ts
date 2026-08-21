/**
 * Why deleting is blocked on the project currently scoping the app. Shared by the
 * card trash can and the detail-page FAB so the two can't drift apart.
 */
export const ACTIVE_PROJECT_DELETE_BLOCKED =
  'Active project — cannot be deleted. Switch to another project first.';

/** What a user actually loses when a project goes away. */
export const PROJECT_DELETE_WARNING =
  'Everyone on this project loses access. Its endpoints, tests, and results stop showing up in the app.';
