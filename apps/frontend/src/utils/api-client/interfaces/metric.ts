import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Tag } from './tag';
import { PaginationParams } from './pagination';
import { Model } from './model';

// 'binary' is returned by the backend (ScoreType.BINARY) but was missing here.
// Note src/constants/score-types.ts deliberately still omits it: that constant
// drives the metric creation form, and offering binary there is a separate change.
export type ScoreType = 'binary' | 'numeric' | 'categorical';

export type ThresholdOperator = '=' | '<' | '>' | '<=' | '>=' | '!=';

/** What a metric judges; the choices and labels come from `GET /metrics/targets`. */
export type MetricTargetOn =
  | 'turn'
  | 'conversation'
  | 'run'
  | 'tool_call'
  | 'retrieval'
  | 'model_call'
  | 'agent'
  | 'guardrail'
  | 'span';

export type MetricTargetAggregate = 'all' | 'any' | 'share';

export type MetricTargetAttributeValue = string | number | boolean;

/**
 * One condition a span must meet. `field` is a special field from
 * `GET /metrics/targets` or a span attribute key; `op` one of its operators.
 */
export interface MetricTargetCondition {
  field: string;
  op: string;
  /** Left out for an operator that takes no value; a list for `in`/`not_in`. */
  value?: MetricTargetAttributeValue | MetricTargetAttributeValue[] | null;
}

/**
 * The older `where` form: attribute values by key, a list meaning any of them.
 * The API stores conditions now, so only rows written before that carry it.
 */
export type MetricTargetLegacyWhere = Record<
  string,
  MetricTargetAttributeValue | MetricTargetAttributeValue[]
>;

/** What a per-unit target hands the metric as input and output. */
export interface MetricTargetRead {
  input?: string;
  output?: string;
}

export interface MetricTarget {
  on: MetricTargetOn | string;
  /** Per-span presets only: only spans with this tool, agent or model name. */
  name?: string;
  /** Per-span targets only: only spans inside the agent with this name. */
  within?: string;
  /** Conditions every unit's root span must meet, all of them. */
  where?: MetricTargetCondition[] | MetricTargetLegacyWhere;
  read?: MetricTargetRead;
  aggregate?: MetricTargetAggregate;
  min_share?: number;
}

/** `config` holds the target plus the metric class's own settings. A PUT replaces all of it. */
export interface MetricConfig {
  target?: MetricTarget;
  [key: string]: unknown;
}

/** One entry of the target registry, in the backend's order. */
export interface MetricTargetChoice {
  on: MetricTargetOn | string;
  label: string;
  description: string;
  per_span: boolean;
  /** The span type a per-span target judges one by one, e.g. `tool.invoke`. */
  span_kind?: string | null;
}

/** What a condition's operator compares with: `ValueType` in the SDK. */
export type ConditionValueType =
  | 'none'
  | 'number'
  | 'list'
  | 'text'
  | 'pattern';

/** An operator a target condition takes. */
export interface ConditionOperatorChoice {
  op: string;
  takes_value: boolean;
  value_type: ConditionValueType | string;
}

/** A field a condition reads besides span attributes (`kind`, `name`, ...). */
export interface SpecialFieldChoice {
  field: string;
  label: string;
}

/** What `read` may name besides an attribute key or an event (`input`, ...). */
export interface ReaderChoice {
  reader: string;
  label: string;
}

/** `GET /metrics/targets`: the presets, the parts of a condition, and what `read` may name. */
export interface MetricTargetOptions {
  targets: MetricTargetChoice[];
  operators: ConditionOperatorChoice[];
  special_fields: SpecialFieldChoice[];
  readers: ReaderChoice[];
  /** `read` names an event's value with this prefix: `event:ai.retrieval.query`. */
  event_prefix: string | null;
}

/** Body of `POST /metrics/targets/preview`. */
export interface MetricTargetPreviewRequest {
  project_id: string;
  target: MetricTarget;
  traces?: number;
}

/** One unit a previewed target picked, its input and output cut short. */
export interface MetricTargetPreviewSample {
  trace_id: string;
  span_id?: string | null;
  name?: string | null;
  input?: string | null;
  output?: string | null;
  duration_ms?: number | null;
  status?: string | null;
}

/** What a target picks in the project's latest traces. */
export interface MetricTargetPreview {
  traces: number;
  matching_traces: number;
  units: number;
  not_applicable_traces: number;
  samples: MetricTargetPreviewSample[];
  /** The draft target in words, as `Metric.target_summary` reads. */
  target_summary?: string | null;
  target_summary_short?: string | null;
}

export interface Metric {
  id: UUID;
  name: string;
  description: string;
  tags: Tag[];
  evaluation_prompt: string;
  evaluation_steps: string;
  reasoning: string;
  score_type: ScoreType;
  min_score?: number;
  max_score?: number;
  categories?: string[]; // List of valid categories for categorical metrics
  passing_categories?: string[]; // Categories that indicate pass
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation: string;
  ground_truth_required: boolean;
  /** Whether evaluating needs retrieved context alongside input and output. */
  context_required?: boolean;
  /** The implementing class, e.g. a framework metric's DeepEvalAnswerRelevancy. */
  class_name?: string | null;
  evaluation_examples?: string;
  config?: MetricConfig | null;
  /** Targets this metric can take, in registry order; null when unknown. */
  supported_targets?: string[] | null;
  /**
   * What the metric judges, in words, names in backticks: "each tool call named
   * `issue_refund`". A card puts "on " in front of the short form.
   */
  target_summary?: string | null;
  target_summary_short?: string | null;
  organization_id?: UUID;

  // References (now always included from backend)
  metric_type: TypeLookup;
  backend_type: TypeLookup;
  model_id?: UUID;
}

/** A created or updated metric, with what the write noticed but didn't refuse. */
export interface MetricSaved extends Metric {
  /** Such as a condition on an attribute key no recent span carries. */
  warnings?: string[];
}

export interface MetricCreate {
  name: string;
  description?: string;
  tags: string[];
  evaluation_prompt: string;
  evaluation_steps?: string;
  evaluation_examples?: string;
  reasoning?: string;
  score_type: ScoreType;
  min_score?: number;
  max_score?: number;
  reference_score?: string; // @deprecated: kept for transition, use categories instead
  categories?: string[]; // List of valid categories for categorical metrics
  passing_categories?: string[]; // Categories that indicate pass
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation: string;
  ground_truth_required?: boolean;
  /** The SDK class a built-in metric is made from, such as a rule's. */
  class_name?: string;
  config?: MetricConfig | null;
  // ID-based fields (preferred for frontend)
  metric_type_id?: UUID;
  backend_type_id?: UUID;
  status_id?: UUID;
  assignee_id?: UUID;
  owner_id?: UUID;
  model_id?: UUID;
  // String-based fields (for SDK compatibility)
  metric_type?: string;
  backend_type?: string;
}

export interface MetricUpdate {
  name?: string;
  description?: string;
  tags?: Tag[];
  evaluation_prompt?: string;
  evaluation_steps?: string;
  evaluation_examples?: string;
  reasoning?: string;
  score_type?: ScoreType;
  min_score?: number;
  max_score?: number;
  reference_score?: string; // @deprecated: kept for transition, use categories instead
  categories?: string[]; // List of valid categories for categorical metrics
  passing_categories?: string[]; // Categories that indicate pass
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation?: string;
  ground_truth_required?: boolean;
  config?: MetricConfig | null;
  metric_type_id?: UUID;
  backend_type_id?: UUID;
  status_id?: UUID;
  assignee_id?: UUID;
  owner_id?: UUID;
  model_id?: UUID;
}

export interface RequirementReference {
  id: UUID;
  name: string;
  description?: string;
  // Add other essential requirement fields as needed
}

export interface MetricDetail extends Metric {
  requirements?: RequirementReference[];
  model?: Model;
  /** Set by the list endpoint only; null elsewhere. */
  tuning_cases_count?: number | null;
}

export interface MetricQueryParams extends PaginationParams {
  status?: string;
  type?: string;
  /**
   * OData $select expression -- comma-separated top-level field names to
   * return (id is always included). Trims the response to only what the
   * caller renders; see backend utils/odata.py::apply_select.
   */
  $select?: string;
  /** Comma-separated target `on` values, such as `turn,conversation`. */
  target?: string;
}
