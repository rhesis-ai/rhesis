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

/** Map of label name → ``(experiment_id, version)`` pair. */
export interface LabelPointer {
  experiment_id: string;
  version: string;
}

export interface ProjectLabels {
  labels: Record<string, LabelPointer>;
}

export interface LabelBindRequest {
  experiment_id: string;
  version: string;
}

export interface ResolveResponse {
  schema: ParameterSchema;
  values: Record<string, ParameterValue>;
  experiment_id: string;
  version: string;
  source: 'label' | 'experiment_id' | 'version';
  source_label?: string | null;
}

/**
 * Well-known label names rendered in every project's labels block,
 * even when unbound. Custom names are still freely user-creatable;
 * this list is the closed set of names the frontend overlays for
 * first-class display. Mirrors
 * ``WELL_KNOWN_LABELS`` in
 * ``apps/backend/src/rhesis/backend/app/schemas/parameters.py``.
 */
export const WELL_KNOWN_LABELS: ReadonlyArray<string> = [
  'default',
  'production',
  'staging',
];

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
