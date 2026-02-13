import { UUID } from 'crypto';
import { User } from './user';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { Tag } from './tag';
import { PaginationParams } from './pagination';
import { Model } from './model';
import { Organization } from './organization';

export type ScoreType = 'numeric' | 'categorical';

export type ThresholdOperator = '=' | '<' | '>' | '<=' | '>=' | '!=';

export type MetricScope = 'Single-Turn' | 'Multi-Turn';

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
  reference_score?: string; // @deprecated: kept for transition, use categories instead
  categories?: string[]; // List of valid categories for categorical metrics
  passing_categories?: string[]; // Categories that indicate pass
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation: string;
  ground_truth_required: boolean;
  context_required: boolean;
  class_name?: string;
  evaluation_examples?: string;
  metric_scope?: MetricScope[];
  created_at: string;
  updated_at: string;
  priority?: number;
  organization_id?: UUID;
  user_id?: UUID;

  // References (now always included from backend)
  metric_type: TypeLookup;
  backend_type: TypeLookup;
  status?: Status;
  assignee?: User;
  owner?: User;
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

export interface BehaviorReference {
  id: UUID;
  name: string;
  description?: string;
  // Add other essential behavior fields as needed
}

export interface MetricDetail extends Metric {
  nano_id?: string;
  behaviors?: BehaviorReference[] | string[]; // Allow both reference objects and UUID strings
  model?: Model; // Include the full model object when available
  user?: User; // Include the creating user
  organization?: Organization; // Include the organization
  comments?: unknown; // Comments data (can be null)
}

export interface MetricsResponse {
  metrics: MetricDetail[];
  totalCount: number;
}

export interface MetricQueryParams extends PaginationParams {
  status?: string;
  type?: string;
}
