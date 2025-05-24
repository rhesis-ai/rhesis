import { UUID } from 'crypto';
import { User } from './user';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { PaginationParams } from './pagination';

export type ScoreType = 'binary' | 'numeric';

export type ThresholdOperator = '=' | '<' | '>' | '<=' | '>=' | '!=';

export interface Metric {
  id: UUID;
  name: string;
  description: string;
  tags: string[];
  evaluation_prompt: string;
  evaluation_steps: string;
  reasoning: string;
  score_type: ScoreType;
  min_score?: number;
  max_score?: number;
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation: string;
  ground_truth_required: boolean;
  context_required: boolean;
  class_name?: string;
  evaluation_examples?: string;
  created_at: string;
  updated_at: string;
  
  // References
  metric_type?: TypeLookup;
  backend_type?: TypeLookup;
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
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation: string;
  ground_truth_required?: boolean;
  metric_type_id?: UUID;
  backend_type_id?: UUID;
  status_id?: UUID;
  assignee_id?: UUID;
  owner_id?: UUID;
  model_id?: UUID;
}

export interface MetricUpdate {
  name?: string;
  description?: string;
  tags?: string[];
  evaluation_prompt?: string;
  evaluation_steps?: string;
  evaluation_examples?: string;
  reasoning?: string;
  score_type?: ScoreType;
  min_score?: number;
  max_score?: number;
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation?: string;
  ground_truth_required?: boolean;
  metric_type_id?: UUID;
  backend_type_id?: UUID;
  status_id?: UUID;
  assignee_id?: UUID;
  owner_id?: UUID;
  model_id?: UUID;
}

export interface MetricDetail extends Metric {
  behaviors: UUID[];
}

export interface MetricsResponse {
  metrics: MetricDetail[];
  totalCount: number;
}

export interface MetricQueryParams extends PaginationParams {
  status?: string;
  type?: string;
} 