/**
 * Frontend capability mirror.
 *
 * Mirrors the backend `Permission` catalog in
 * `apps/backend/src/rhesis/backend/app/auth/capabilities.py`.
 * Not authoritative — the backend decides; this file provides typed constants,
 * human labels, area grouping, and level derivation for the role editor and
 * permission UI.
 *
 * Keep the `Capability` constants and `RESOURCE_AREA` map in sync when new
 * resources are added to the backend `Permission` enum.
 */

// ---------------------------------------------------------------------------
// Capability constants (mirror backend Permission enum)
// ---------------------------------------------------------------------------

export const Capability = {
  TestSet: {
    READ: 'test_set:read',
    CREATE: 'test_set:create',
    UPDATE: 'test_set:update',
    DELETE: 'test_set:delete',
    GENERATE: 'test_set:generate',
    EXECUTE: 'test_set:execute',
    EXPORT: 'test_set:export',
  },
  Test: {
    READ: 'test:read',
    CREATE: 'test:create',
    UPDATE: 'test:update',
    DELETE: 'test:delete',
  },
  TestConfiguration: {
    READ: 'test_configuration:read',
    CREATE: 'test_configuration:create',
    UPDATE: 'test_configuration:update',
    DELETE: 'test_configuration:delete',
  },
  TestRun: {
    READ: 'test_run:read',
    CREATE: 'test_run:create',
    UPDATE: 'test_run:update',
    DELETE: 'test_run:delete',
    EXECUTE: 'test_run:execute',
    /**
     * Role-editor only — do NOT use in `can(subject, …)` / `useCan()` checks.
     * The backend collapses this to the base cap (`test_run:delete`) in
     * `permitted_actions`; use `Capability.TestRun.DELETE` for affordance checks.
     */
    DELETE_OWN: 'test_run:delete:own',
  },
  TestResult: {
    READ: 'test_result:read',
    UPDATE: 'test_result:update',
    DELETE: 'test_result:delete',
    /**
     * Role-editor only — do NOT use in `can(subject, …)` / `useCan()` checks.
     * The backend collapses these to base caps in `permitted_actions`;
     * use `Capability.TestResult.UPDATE` / `DELETE` for affordance checks.
     */
    UPDATE_OWN: 'test_result:update:own',
    DELETE_OWN: 'test_result:delete:own',
  },
  Experiment: {
    READ: 'experiment:read',
    CREATE: 'experiment:create',
    UPDATE: 'experiment:update',
    DELETE: 'experiment:delete',
    /**
     * Role-editor only — do NOT use in `can(subject, …)` / `useCan()` checks.
     * The backend collapses these to base caps in `permitted_actions`;
     * use `Capability.Experiment.UPDATE` / `DELETE` for affordance checks.
     */
    UPDATE_OWN: 'experiment:update:own',
    DELETE_OWN: 'experiment:delete:own',
  },
  Endpoint: {
    READ: 'endpoint:read',
    CREATE: 'endpoint:create',
    UPDATE: 'endpoint:update',
    DELETE: 'endpoint:delete',
  },
  Playground: {
    USE: 'playground:use',
  },
  Comment: {
    READ: 'comment:read',
    CREATE: 'comment:create',
    UPDATE: 'comment:update',
    DELETE: 'comment:delete',
    REACT: 'comment:react',
    /**
     * Role-editor only — do NOT use in `can(subject, …)` / `useCan()` checks.
     * The backend collapses these to base caps in `permitted_actions`;
     * use `Capability.Comment.UPDATE` / `DELETE` for affordance checks.
     */
    UPDATE_OWN: 'comment:update:own',
    DELETE_OWN: 'comment:delete:own',
  },
  Task: {
    READ: 'task:read',
    CREATE: 'task:create',
    UPDATE: 'task:update',
    DELETE: 'task:delete',
    /**
     * Role-editor only — do NOT use in `can(subject, …)` / `useCan()` checks.
     * The backend collapses these to base caps (`task:update`, `task:delete`) in
     * `permitted_actions`; use `Capability.Task.UPDATE` / `DELETE` for affordance checks.
     */
    UPDATE_OWN: 'task:update:own',
    UPDATE_ASSIGNED: 'task:update:assigned',
    DELETE_OWN: 'task:delete:own',
  },
  Source: {
    READ: 'source:read',
    CREATE: 'source:create',
    UPDATE: 'source:update',
    DELETE: 'source:delete',
  },
  Behavior: {
    READ: 'behavior:read',
    CREATE: 'behavior:create',
    UPDATE: 'behavior:update',
    DELETE: 'behavior:delete',
  },
  Tool: {
    READ: 'tool:read',
    CREATE: 'tool:create',
    UPDATE: 'tool:update',
    DELETE: 'tool:delete',
  },
  Explorer: {
    READ: 'explorer:read',
    CREATE: 'explorer:create',
    UPDATE: 'explorer:update',
    DELETE: 'explorer:delete',
  },
  Architect: {
    READ: 'architect:read',
    CREATE: 'architect:create',
    DELETE: 'architect:delete',
  },
  Telemetry: {
    READ: 'telemetry:read',
    CREATE: 'telemetry:create',
    UPDATE: 'telemetry:update',
    DELETE: 'telemetry:delete',
  },
  Preflight: {
    CREATE: 'preflight:create',
  },
  File: {
    READ: 'file:read',
    CREATE: 'file:create',
    UPDATE: 'file:update',
    DELETE: 'file:delete',
    IMPORT: 'file:import',
  },
  Garak: {
    READ: 'garak:read',
    CREATE: 'garak:create',
  },
  Metric: {
    READ: 'metric:read',
    CREATE: 'metric:create',
    UPDATE: 'metric:update',
    DELETE: 'metric:delete',
  },
  Model: {
    READ: 'model:read',
    CREATE: 'model:create',
    UPDATE: 'model:update',
    DELETE: 'model:delete',
  },
  Project: {
    READ: 'project:read',
    CREATE: 'project:create',
    UPDATE: 'project:update',
  },
  ProjectMember: {
    READ: 'project_member:read',
    MANAGE: 'project_member:manage',
  },
  Organization: {
    READ: 'organization:read',
    UPDATE: 'organization:update',
  },
  Member: {
    READ: 'member:read',
    CREATE: 'member:create',
    DELETE: 'member:delete',
    MANAGE: 'member:manage',
    UPDATE: 'member:update',
  },
  Role: {
    READ: 'role:read',
    MANAGE: 'role:manage',
  },
  Token: {
    MANAGE: 'token:manage',
  },
  Recycle: {
    VIEW: 'recycle:view',
    RESTORE: 'recycle:restore',
    PURGE: 'recycle:purge',
  },
  SSO: {
    MANAGE: 'sso:manage',
  },
  ApiClients: {
    MANAGE: 'api_clients:manage',
  },
  Polyphemus: {
    REQUEST: 'polyphemus:request',
  },
} as const;

// ---------------------------------------------------------------------------
// Human labels
//
// NOTE: the graded role model (capability areas + None/View/Edit/Manage levels)
// is an EE concern — it exists only to drive the custom-role editor. Community
// is a binary owner/member system with no graded roles, so that model is NOT
// defined here; it lives with the role editor in `ee/frontend` (see
// rbac_frontend_authoring_ui.plan.md). Core only needs the typed `Capability`
// constants and these human labels (nav lock tooltips, Access-Denied).
// ---------------------------------------------------------------------------

export const CAPABILITY_LABELS: Record<string, string> = {
  // Test sets
  'test_set:read': 'View test sets',
  'test_set:create': 'Create test sets',
  'test_set:update': 'Edit test sets',
  'test_set:delete': 'Delete test sets',
  'test_set:generate': 'Generate tests',
  'test_set:execute': 'Run test sets',
  'test_set:export': 'Export test sets',
  // Tests
  'test:read': 'View tests',
  'test:create': 'Create tests',
  'test:update': 'Edit tests',
  'test:delete': 'Delete tests',
  // Test configurations
  'test_configuration:read': 'View test configurations',
  'test_configuration:create': 'Create test configurations',
  'test_configuration:update': 'Edit test configurations',
  'test_configuration:delete': 'Delete test configurations',
  // Test runs
  'test_run:read': 'View test runs',
  'test_run:create': 'Create test runs',
  'test_run:update': 'Edit test runs',
  'test_run:delete': 'Delete test runs',
  'test_run:execute': 'Execute test runs',
  'test_run:delete:own': 'Delete own test runs',
  // Test results
  'test_result:read': 'View test results',
  'test_result:update': 'Update test results',
  'test_result:update:own': 'Edit own reviews',
  'test_result:delete:own': 'Delete own reviews',
  // Experiments
  'experiment:read': 'View experiments',
  'experiment:create': 'Create experiments',
  'experiment:update': 'Edit experiments',
  'experiment:delete': 'Delete experiments',
  'experiment:update:own': 'Edit own experiments',
  'experiment:delete:own': 'Delete own experiments',
  // Endpoints
  'endpoint:read': 'View endpoints',
  'endpoint:create': 'Create endpoints',
  'endpoint:update': 'Edit endpoints',
  'endpoint:delete': 'Delete endpoints',
  // Playground
  'playground:use': 'Use playground',
  // Comments
  'comment:read': 'View comments',
  'comment:create': 'Post comments',
  'comment:update': 'Edit any comment',
  'comment:delete': 'Delete any comment',
  'comment:react': 'React to comments',
  'comment:update:own': 'Edit own comments',
  'comment:delete:own': 'Delete own comments',
  // Tasks
  'task:read': 'View tasks',
  'task:create': 'Create tasks',
  'task:update': 'Edit tasks',
  'task:delete': 'Delete tasks',
  'task:update:own': 'Edit own tasks',
  'task:update:assigned': 'Edit assigned tasks',
  'task:delete:own': 'Delete own tasks',
  // Sources (knowledge base)
  'source:read': 'View knowledge sources',
  'source:create': 'Upload knowledge sources',
  'source:update': 'Edit knowledge sources',
  'source:delete': 'Delete knowledge sources',
  // Behaviors
  'behavior:read': 'View behaviors',
  'behavior:create': 'Create behaviors',
  'behavior:update': 'Edit behaviors',
  'behavior:delete': 'Delete behaviors',
  // Tools
  'tool:read': 'View tool connections',
  'tool:create': 'Add tool connections',
  'tool:update': 'Edit tool connections',
  'tool:delete': 'Delete tool connections',
  // Explorer
  'explorer:read': 'View explorer sessions',
  'explorer:create': 'Create explorer sessions',
  'explorer:update': 'Edit explorer sessions',
  'explorer:delete': 'Delete explorer sessions',
  // Architect
  'architect:read': 'View Architect sessions',
  'architect:create': 'Start Architect sessions',
  'architect:delete': 'Delete Architect sessions',
  // Telemetry (traces)
  'telemetry:read': 'View traces',
  'telemetry:create': 'Create traces',
  'telemetry:update': 'Update traces',
  'telemetry:delete': 'Delete traces',
  // Preflight
  'preflight:create': 'Run preflight checks',
  // Files
  'file:read': 'View files',
  'file:create': 'Upload files',
  'file:update': 'Update files',
  'file:delete': 'Delete files',
  'file:import': 'Import files',
  // Garak
  'garak:read': 'View Garak probes',
  'garak:create': 'Import Garak probes',
  // Metrics
  'metric:read': 'View metrics',
  'metric:create': 'Create metrics',
  'metric:update': 'Edit metrics',
  'metric:delete': 'Delete metrics',
  // Models
  'model:read': 'View models',
  'model:create': 'Create models',
  'model:update': 'Edit models',
  'model:delete': 'Delete models',
  // Projects
  'project:read': 'View projects',
  'project:create': 'Create projects',
  'project:update': 'Edit projects',
  'project_member:read': 'View project members',
  'project_member:manage': 'Manage project members',
  // Organization
  'organization:read': 'View organization settings',
  'organization:update': 'Edit organization settings',
  // Members
  'member:read': 'View members',
  'member:create': 'Invite members',
  'member:delete': 'Remove members',
  'member:manage': 'Manage org membership',
  'member:update': 'Edit member profiles',
  // Roles
  'role:read': 'View roles',
  'role:manage': 'Manage roles',
  // Tokens
  'token:manage': 'Manage API tokens',
  // Recycle bin
  'recycle:view': 'View recycle bin',
  'recycle:restore': 'Restore deleted items',
  'recycle:purge': 'Permanently delete items',
  // EE
  'sso:manage': 'Manage SSO configuration',
  'api_clients:manage': 'Manage API clients',
  'polyphemus:request': 'Request Polyphemus access',
};
