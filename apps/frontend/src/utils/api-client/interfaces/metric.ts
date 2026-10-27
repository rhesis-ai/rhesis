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
  | 'guardrail';

export type MetricTargetAggregate = 'all' | 'any' | 'share';

export interface MetricTarget {
  on: MetricTargetOn | string;
  /** Per-span targets only: only spans with this tool, agent or model name. */
  name?: string;
  within?: string;
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
  evaluation_examples?: string;
  config?: MetricConfig | null;
  /** Targets this metric can take, in registry order; null when unknown. */
  supported_targets?: string[] | null;
  organization_id?: UUID;

  // References (now always included from backend)
  metric_type: TypeLookup;
  backend_type: TypeLookup;
  model_id?: UUID;
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
