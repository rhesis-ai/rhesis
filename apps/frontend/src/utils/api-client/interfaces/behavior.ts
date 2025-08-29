import { UUID } from 'crypto';

export interface BehaviorBase {
  name: string;
  description?: string | null;
  status_id?: UUID | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
}

export interface BehaviorCreate extends BehaviorBase {}

export interface BehaviorUpdate extends Partial<BehaviorBase> {}

export interface Behavior extends BehaviorBase {
  id: UUID;
  metrics?: MetricReference[]; // Optional metrics when using include=metrics
}

export interface BehaviorWithMetrics extends BehaviorBase {
  id: UUID;
  metrics: MetricReference[]; // Always present when explicitly requesting with metrics
}

export interface MetricReference {
  id: UUID;
  name: string;
  description: string;
  score_type: string;
  evaluation_prompt?: string;
  explanation?: string;
  // Add other essential metric fields as needed
}

export interface BehaviorsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: string;
  $filter?: string;
  include?: string; // New: for including relationships like 'metrics'
} 