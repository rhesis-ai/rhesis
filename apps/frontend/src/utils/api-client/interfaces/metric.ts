import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Tag } from './tag';
import { PaginationParams } from './pagination';
import { Model } from './model';
import { MetricScopeValue } from '@/constants/metric-scopes';

// 'binary' is returned by the backend (ScoreType.BINARY) but was missing here.
// Note src/constants/score-types.ts deliberately still omits it: that constant
// drives the metric creation form, and offering binary there is a separate change.
export type ScoreType = 'binary' | 'numeric' | 'categorical';

export type ThresholdOperator = '=' | '<' | '>' | '<=' | '>=' | '!=';

export type MetricScope = MetricScopeValue;

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
  metric_scope?: MetricScope[];
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
  metric_scope?: MetricScope[];
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
  metric_scope?: MetricScope[];
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
  /**
   * Comma-separated metric scopes (JSONB array contains filter).
   * Matches metrics whose metric_scope array contains any of the values.
   */
  metric_scope?: string;
}
