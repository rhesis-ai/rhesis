/**
 * Frontend mirrors of the backend's parameter-management Pydantic models.
 *
 * The wire format is the single source of truth: each value variant is
 * a discriminated union with a literal `type` field. Components render
 * type-aware inputs by switching on `type`; storage round-trips
 * untouched through the single `PUT /projects/{id}/parameters/schema`
 * endpoint.
 *
 * Keep these in lockstep with
 * `apps/backend/src/rhesis/backend/app/schemas/parameters.py`.
 */

import { UUID } from 'crypto';

/** Closed set of supported parameter types. Mirrors the backend literal. */
export type ParameterType =
  | 'text'
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'enum'
  | 'model_ref'
  | 'secret_ref';

export interface TextValue {
  type: 'text';
  value: string;
}
export interface StringValue {
  type: 'string';
  value: string;
}
export interface IntegerValue {
  type: 'integer';
  value: number;
}
export interface NumberValue {
  type: 'number';
  value: number;
}
export interface BooleanValue {
  type: 'boolean';
  value: boolean;
}
export interface EnumValue {
  type: 'enum';
  value: string;
}
export interface ModelRefValue {
  type: 'model_ref';
  value: UUID | string;
}
export interface SecretRefValue {
  type: 'secret_ref';
  value: UUID | string;
}

/** Discriminated union of every value variant; switch on `.type`. */
export type ParameterValue =
  | TextValue
  | StringValue
  | IntegerValue
  | NumberValue
  | BooleanValue
  | EnumValue
  | ModelRefValue
  | SecretRefValue;

/** One named slot in a project's parameter schema. */
export interface ParameterField {
  name: string;
  type: ParameterType;
  description?: string | null;
  required?: boolean;
  default?: ParameterValue | null;
  options?: string[] | null;
  display_order?: number;
}

/** Full parameter schema for a project. */
export interface ParameterSchema {
  fields: ParameterField[];
}

/** Returns a typed empty schema; consumers prefer this over inline literals. */
export function emptyParameterSchema(): ParameterSchema {
  return { fields: [] };
}

/**
 * One immutable version inside an experiment's history.
 *
 * The ``version`` is a content hash and the natural identifier for
 * this version both in the API and on test runs that snapshot it.
 */
export interface ExperimentVersion {
  version: string;
  schema_fingerprint: string;
  values: Record<string, ParameterValue>;
  parent_version?: string | null;
  message?: string | null;
  created_at: string;
  created_by_user_id: string;
}

export type ExperimentVisibility = 'private' | 'shared';

/** Compact list / single shape — omits the inline ``versions`` array. */
export interface ExperimentRead {
  id: string;
  project_id: string;
  owner_user_id: string;
  organization_id?: string | null;
  project_name?: string | null;
  name: string;
  description?: string | null;
  visibility: ExperimentVisibility;
  versions_count: number;
  latest_version?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Full detail shape including the versions array. */
export interface ExperimentDetail extends ExperimentRead {
  versions: ExperimentVersion[];
}

export interface ExperimentCreate {
  name: string;
  description?: string | null;
  visibility?: ExperimentVisibility;
}

export interface ExperimentUpdate {
  name?: string;
  description?: string | null;
  visibility?: ExperimentVisibility;
}

export interface ExperimentVersionCreate {
  values: Record<string, unknown>;
  message?: string | null;
  parent_version?: string | null;
}

/** Map of environment name → ``(experiment_id, version)`` pair. */
export interface EnvironmentPointer {
  experiment_id: string;
  version: string;
}

/**
 * Project-scoped map of environment name → pointer.
 *
 * A ``null`` value means the user registered a custom environment name
 * via ``POST /environments`` but hasn't promoted an experiment onto it
 * yet. The UI renders those rows the same way built-in unbound names
 * render: name visible, "Unbound" pointer cell, Promote button enabled.
 */
export interface ProjectEnvironments {
  environments: Record<string, EnvironmentPointer | null>;
}

export interface EnvironmentBindRequest {
  experiment_id: string;
  version: string;
}

/** Body for ``POST /projects/{id}/parameters/environments``. */
export interface EnvironmentRegisterRequest {
  name: string;
}

export interface ResolveResponse {
  schema: ParameterSchema;
  values: Record<string, ParameterValue>;
  experiment_id: string;
  version: string;
  source: 'environment' | 'experiment_id' | 'version';
  source_environment?: string | null;
}

/**
 * Namespace for the environment names the platform always recognises.
 *
 * Mirrors :class:`BuiltInEnvironment` in
 * ``apps/backend/src/rhesis/backend/app/schemas/parameters.py``. Keep
 * in lockstep.
 *
 * Environment names themselves remain free-form strings — any value
 * matching ``ENVIRONMENT_NAME_PATTERN`` is creatable through
 * ``POST /environments``. This object is *not* a type, just a tidy
 * set of literals so call sites don't repeat the names inline.
 *
 * Two members carry extra meaning beyond "always rendered":
 *
 * - ``DEFAULT`` is the resolver's implicit fallback.
 * - ``PRODUCTION`` triggers the UI's deployment-impact warning at
 *   promote time.
 *
 * Use ``BuiltInEnvironment.ALL`` to iterate the full set.
 */
export const BuiltInEnvironment = {
  DEFAULT: 'default',
  DEVELOPMENT: 'development',
  STAGING: 'staging',
  PRODUCTION: 'production',
  /** Ordered list of every built-in name; iterate when you need the full set. */
  ALL: ['default', 'development', 'staging', 'production'] as ReadonlyArray<string>,
} as const;

/**
 * Hard upper bound on environment-name length. Mirror of
 * ``ENVIRONMENT_NAME_MAX_LENGTH`` in the backend
 * ``schemas/parameters.py``. Keep in lockstep.
 */
export const ENVIRONMENT_NAME_MAX_LENGTH = 63;

/**
 * Allowed shape for environment names. Lowercase alphanumeric plus
 * ``.``, ``_``, ``-`` as inner punctuation, must start with an
 * alphanumeric. Mirror of ``ENVIRONMENT_NAME_PATTERN`` in the backend
 * ``schemas/parameters.py``; keep in lockstep.
 */
export const ENVIRONMENT_NAME_PATTERN = /^[a-z0-9][a-z0-9._-]{0,62}$/;

/**
 * Validate ``name`` against the same rule the backend enforces on
 * ``PUT /environments/{name}``. Returns ``null`` if valid, otherwise a
 * short, user-facing error message suitable for an MUI ``helperText``
 * or ``error`` slot.
 */
export function validateEnvironmentName(name: string): string | null {
  if (!name) {
    return 'Name is required';
  }
  if (name.length > ENVIRONMENT_NAME_MAX_LENGTH) {
    return `Name must be at most ${ENVIRONMENT_NAME_MAX_LENGTH} characters`;
  }
  if (!ENVIRONMENT_NAME_PATTERN.test(name)) {
    return (
      'Use lowercase letters, digits, ".", "_" or "-". Must start with a ' +
      'letter or digit.'
    );
  }
  return null;
}

/** A short, display-friendly hash chip (e.g. ``v_a3f9b8``). */
export function shortVersion(version: string | null | undefined): string {
  if (!version) return '';
  // Hashes are formatted as ``v_<sha>``; trim to v_ + 6 chars so the
  // chip stays readable in dense tables.
  if (version.startsWith('v_')) {
    return `v_${version.slice(2, 8)}`;
  }
  return version.slice(0, 8);
}

export interface ExperimentResultsRunItem {
  id: string;
  name?: string;
  created_at?: string;
  attributes?: Record<string, any>;
  experiment_summary?: {
    id: string;
    name: string;
    version: string;
    source_environment?: string | null;
    visibility: ExperimentVisibility;
  } | null;
}

export interface ExperimentResultsVersionItem {
  version: string;
  runs: ExperimentResultsRunItem[];
  total_tests: number;
  diff: Record<string, { before: any; after: any }>;
}

export interface ExperimentResultsByRun {
  items: ExperimentResultsRunItem[];
}

export interface ExperimentResultsByVersion {
  items: ExperimentResultsVersionItem[];
}
