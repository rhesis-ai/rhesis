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
    DELETE_OWN: 'test_run:delete:own',
  },
  TestResult: {
    READ: 'test_result:read',
    UPDATE: 'test_result:update',
    UPDATE_OWN: 'test_result:update:own',
    DELETE_OWN: 'test_result:delete:own',
  },
  Experiment: {
    READ: 'experiment:read',
    CREATE: 'experiment:create',
    UPDATE: 'experiment:update',
    DELETE: 'experiment:delete',
    UPDATE_OWN: 'experiment:update:own',
    DELETE_OWN: 'experiment:delete:own',
  },
  Endpoint: {
    READ: 'endpoint:read',
    CREATE: 'endpoint:create',
    UPDATE: 'endpoint:update',
    DELETE: 'endpoint:delete',
  },
  Comment: {
    READ: 'comment:read',
    CREATE: 'comment:create',
    UPDATE: 'comment:update',
    DELETE: 'comment:delete',
    REACT: 'comment:react',
    UPDATE_OWN: 'comment:update:own',
    DELETE_OWN: 'comment:delete:own',
  },
  Task: {
    READ: 'task:read',
    CREATE: 'task:create',
    UPDATE: 'task:update',
    DELETE: 'task:delete',
  },
  Architect: {
    READ: 'architect:read',
    CREATE: 'architect:create',
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
  // Architect
  'architect:read': 'View Architect sessions',
  'architect:create': 'Start Architect sessions',
  // Preflight
  'preflight:create': 'Run preflight checks',
  // Files
  'file:read': 'View files',
  'file:create': 'Upload files',
  'file:update': 'Update files',
  'file:delete': 'Delete files',
  'file:import': 'Import files',
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
};
