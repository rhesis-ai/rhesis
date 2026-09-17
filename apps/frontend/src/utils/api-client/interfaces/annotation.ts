import type { WithPermittedActions } from '@/types/affordances';
// Type-only: `isolatedModules` transpiles each file alone, so a value import
// of a Node module that is only ever a type here is left for the bundler to
// resolve.
import type { UUID } from 'crypto';

/**
 * A human judgement on a test result, a trace or a test.
 *
 * Annotations are their own entity, linked to a parent by
 * `(entity_type, entity_id)`. On responses the target is flat
 * (`target_type` / `target_reference`); on writes it is nested under `target`.
 */

export const ANNOTATION_ENTITY_TYPES = {
  TEST_RESULT: 'TestResult',
  TRACE: 'Trace',
  TEST: 'Test',
} as const;

export type AnnotationEntityType =
  (typeof ANNOTATION_ENTITY_TYPES)[keyof typeof ANNOTATION_ENTITY_TYPES];

export const ANNOTATION_ENTITY_LABELS: Record<AnnotationEntityType, string> = {
  [ANNOTATION_ENTITY_TYPES.TEST_RESULT]: 'Test Result',
  [ANNOTATION_ENTITY_TYPES.TRACE]: 'Trace',
  [ANNOTATION_ENTITY_TYPES.TEST]: 'Test',
};

export const ANNOTATION_TARGET_TYPES = {
  TEST_RESULT: 'test_result',
  TRACE: 'trace',
  TEST: 'test',
  TURN: 'turn',
  METRIC: 'metric',
} as const;

export type AnnotationTargetType =
  (typeof ANNOTATION_TARGET_TYPES)[keyof typeof ANNOTATION_TARGET_TYPES];

export const ANNOTATION_TARGET_LABELS: Record<AnnotationTargetType, string> = {
  [ANNOTATION_TARGET_TYPES.TEST_RESULT]: 'Output',
  [ANNOTATION_TARGET_TYPES.TRACE]: 'Trace',
  [ANNOTATION_TARGET_TYPES.TEST]: 'Test',
  [ANNOTATION_TARGET_TYPES.TURN]: 'Turn',
  [ANNOTATION_TARGET_TYPES.METRIC]: 'Metric',
};

/** The entity-level target for each annotatable parent type. */
export const ENTITY_LEVEL_TARGETS: Record<
  AnnotationEntityType,
  AnnotationTargetType
> = {
  [ANNOTATION_ENTITY_TYPES.TEST_RESULT]: ANNOTATION_TARGET_TYPES.TEST_RESULT,
  [ANNOTATION_ENTITY_TYPES.TRACE]: ANNOTATION_TARGET_TYPES.TRACE,
  [ANNOTATION_ENTITY_TYPES.TEST]: ANNOTATION_TARGET_TYPES.TEST,
};

export interface AnnotationStatus {
  id?: UUID;
  name?: string;
}

/**
 * The status as it arrives *embedded in a parent payload*, which names the id
 * `status_id` rather than `id`. Distinct from `AnnotationStatus` on purpose:
 * one type covering both would type-check `.id` here and hand back undefined.
 */
export interface AnnotationSummaryStatus {
  status_id?: UUID;
  name?: string;
}

export interface AnnotationUser {
  id?: UUID;
  name?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
}

/** Target as the write endpoints accept it. */
export interface AnnotationTargetInput {
  type: AnnotationTargetType;
  reference?: string | null;
}

/**
 * Where an annotated entity sits, so a row can link back to it. Populated by
 * the list and detail endpoints; absent on writes.
 */
export interface AnnotationContext {
  project_id?: UUID | null;
  test_run_id?: UUID | null;
  test_run_name?: string | null;
  test_set_id?: UUID | null;
  test_result_id?: UUID | null;
  requirement_id?: UUID | null;
  requirement_name?: string | null;
  trace_id?: string | null;
  /** Internal row id of the span. Trace deep links need this, not `trace_id`. */
  trace_db_id?: UUID | null;
  span_name?: string | null;
  /**
   * Set when the annotated entity is a metric's tuning case, which is reached
   * through the metric rather than through its test set.
   */
  metric_id?: UUID | null;
}

export interface Annotation extends WithPermittedActions {
  id: UUID;
  entity_type: AnnotationEntityType;
  entity_id: UUID;
  target_type: AnnotationTargetType;
  target_reference?: string | null;
  status_id: UUID;
  status?: AnnotationStatus;
  user_id: UUID;
  user?: AnnotationUser;
  comments?: string | null;
  resolved: boolean;
  resolved_at?: string | null;
  resolved_by_id?: UUID | null;
  resolved_by?: AnnotationUser;
  attributes?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  context?: AnnotationContext | null;
}

/**
 * One annotation as it arrives embedded on its parent, keyed by target in
 * `annotation_summary`. Thinner than a full row: enough to render an indicator
 * or an "annotated by" line without a second request.
 */
export interface AnnotationSummaryEntry {
  annotation_id: string;
  target_type: AnnotationTargetType;
  reference: string | null;
  status: AnnotationSummaryStatus | null;
  user: AnnotationUser | null;
  comments: string | null;
  updated_at: string;
}

// Request shapes take plain strings: ids reach them from component state and
// route params, not from a typed response.
export interface AnnotationCreate {
  entity_type: AnnotationEntityType;
  entity_id: string;
  status_id: string;
  comments?: string | null;
  target?: AnnotationTargetInput;
  attributes?: Record<string, unknown> | null;
}

export interface AnnotationUpdate {
  status_id?: string;
  comments?: string | null;
  target?: AnnotationTargetInput;
  resolved?: boolean;
  attributes?: Record<string, unknown> | null;
}

export interface AnnotationFacets {
  endpoints: { id: string; name: string }[];
  metrics: string[];
  annotators: { id: string; name: string }[];
  requirements: { id: string; name: string }[];
}

export interface AnnotationsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
  rating?: 'Pass' | 'Fail';
  resolved?: boolean;
  target_type?: AnnotationTargetType;
  entity_type?: AnnotationEntityType;
  test_run_id?: string;
  test_set_id?: string;
  endpoint_id?: string;
  metric?: string;
  annotator_id?: string;
  requirement_id?: string;
  date_from?: string;
  date_to?: string;
  $filter?: string;
}
