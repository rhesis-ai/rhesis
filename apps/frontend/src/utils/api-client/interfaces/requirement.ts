import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { User } from './user';
import { Tag } from './tag';
import type { MetricConfig } from './metric';
import type { Annotation } from './annotation';

export interface RequirementBase {
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
  /** Null clears the field on update. */
  parent_id?: UUID | null;
  impact_id?: UUID | null;
}

export type RequirementCreate = RequirementBase;

export type RequirementUpdate = Partial<RequirementBase>;

export interface Requirement extends RequirementBase {
  id: UUID;
}

export interface RequirementReference {
  id: UUID;
  name: string;
  description?: string | null;
}

export interface RequirementWithMetrics extends RequirementBase {
  id: UUID;
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id: UUID;
  created_at?: string | null;
  updated_at?: string | null;
  user?: User | null;
  metrics: MetricWithRelationships[];
  tags?: Tag[];
  /** Linked tests by type. Only the read endpoints fill it. */
  test_counts?: RequirementTestCounts | null;
  parent?: RequirementParentRef | null;
  impact?: RequirementLookupRef | null;
  sources?: RequirementSourceLink[];
  children_count?: number;
  examples_count?: number;
  review?: RequirementReview | null;
}

/** A linked metric as the requirements list embeds it: no prompt or steps. */
export interface RequirementMetricRef {
  id: UUID;
  name: string;
  description?: string | null;
  score_type?: string | null;
  config?: MetricConfig | null;
  metric_type?: RequirementLookupRef | null;
  backend_type?: RequirementLookupRef | null;
  project_id?: UUID | null;
  class_name?: string | null;
}

/** A row of `GET /requirements/`. The detail response has full metrics. */
export interface RequirementListItem extends Omit<
  RequirementWithMetrics,
  'metrics'
> {
  metrics: RequirementMetricRef[];
}

export interface RequirementParentRef {
  id: UUID;
  name: string;
}

/** A `type_lookup` row as embedded on a requirement (type or impact). */
export interface RequirementLookupRef {
  id: UUID;
  type_name: string;
  type_value: string;
}

/** A knowledge source linked to a requirement, with the note on that link. */
export interface RequirementSourceLink {
  id: UUID;
  title: string;
  url?: string | null;
  source_type?: { id: UUID; type_value: string } | null;
  note?: string | null;
}

export type RequirementReviewHintKind =
  | 'vague_wording'
  | 'unclear_behavior'
  | 'split'
  | 'other';

export interface RequirementReviewHint {
  kind: RequirementReviewHintKind;
  message: string;
  /** Words from the description the hint is about. */
  quote: string | null;
  /** The rewritten description, for `vague_wording` and `unclear_behavior`. */
  suggestion: string | null;
}

/** The stored AI review. `description_hash` tells whether it is outdated. */
export interface RequirementReview {
  reviewed_at: string;
  /** sha256 hex of `name + "\n" + description`. */
  description_hash: string;
  hints: RequirementReviewHint[];
}

export interface RequirementExampleTuningCase {
  metric_id: UUID;
  case_id: UUID;
}

/** An annotation linked to a requirement, with the conversation it judged. */
export interface RequirementExample {
  annotation: Annotation;
  input: string | null;
  output: string | null;
  tuning_cases: RequirementExampleTuningCase[];
}

export interface RequirementTestCounts {
  total: number;
  single_turn: number;
  multi_turn: number;
}

export interface MetricWithRelationships {
  id: UUID;
  name: string;
  description: string;
  score_type: string;
  config?: MetricConfig | null;

  // Required relationship objects (now always included from backend)
  metric_type: TypeLookup;
  backend_type: TypeLookup;

  // Optional relationship objects
  status?: Status | null;
}

/** id + name only -- what filter dropdowns and pickers need. */
export interface RequirementOption {
  id: UUID;
  name: string;
}

export interface RequirementsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
  /** Comma-separated fields to return; `id` is always included. */
  $select?: string;
  include?: string;
}
