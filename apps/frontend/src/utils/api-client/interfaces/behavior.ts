import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { User } from './user';
import { Tag } from './tag';
import { MetricScope } from './metric';

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
  nano_id?: string | null;
  status?: Status | null;
  user?: User | null;
  organization?: Organization | null;
  metrics?: MetricWithRelationships[]; // Optional metrics when using include=metrics
}

export interface Organization {
  id: UUID;
  nano_id?: string | null;
  name: string;
  description: string;
  email: string;
  user_id: UUID;
  tags: Tag[];
}

export interface BehaviorReference {
  id: UUID;
  nano_id?: string | null;
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id: UUID;
  status_id: UUID;
}

export interface MetricWithBehaviors {
  id: UUID;
  nano_id?: string | null;
  name: string;
  description: string;
  evaluation_prompt: string;
  evaluation_steps: string;
  reasoning: string;
  score_type: string;
  min_score?: number | null;
  max_score?: number | null;
  reference_score?: string;
  threshold?: number | null;
  threshold_operator: string;
  explanation: string;
  metric_type_id: UUID;
  backend_type_id: UUID;
  model_id?: UUID | null;
  status_id?: UUID | null;
  assignee_id?: UUID | null;
  owner_id?: UUID | null;
  class_name?: string;
  context_required: boolean;
  ground_truth_required?: boolean; // Add missing property
  evaluation_examples?: string;
  created_at: string;
  updated_at: string;
  tags: Tag[];
  user_id?: UUID | null;
  organization_id: UUID;

  // Related entities
  metric_type: TypeLookup;
  status?: Status | null;
  assignee?: User | null;
  owner?: User | null;
  model?: any | null;
  backend_type: TypeLookup;
  behaviors: BehaviorReference[];
  user?: User | null;
  organization: Organization;
}

export interface BehaviorWithMetrics extends BehaviorBase {
  id: UUID;
  nano_id?: string | null;
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id: UUID;
  status_id: UUID;
  status?: Status | null;
  user?: User | null;
  organization: Organization;
  metrics: MetricWithRelationships[]; // Full metric objects with type relationships
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

export interface MetricWithRelationships {
  id: UUID;
  nano_id?: string | null;
  name: string;
  description: string;
  evaluation_prompt: string;
  evaluation_steps?: string;
  reasoning?: string;
  score_type: string;
  min_score?: number | null;
  max_score?: number | null;
  reference_score?: string;
  threshold?: number | null;
  threshold_operator?: string;
  explanation?: string;
  ground_truth_required?: boolean;
  context_required?: boolean;
  class_name?: string;
  evaluation_examples?: string;
  metric_scope?: MetricScope[];
  user_id?: UUID | null;
  organization_id?: UUID | null;
  status_id?: UUID | null;
  tags?: Tag[];

  // Required relationship objects (now always included from backend)
  metric_type: TypeLookup;
  backend_type: TypeLookup;

  // Optional relationship objects
  status?: Status | null;
  assignee?: User | null;
  owner?: User | null;
  model?: any | null;
}

export interface BehaviorsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: string;
  $filter?: string;
  include?: string; // New: for including relationships like 'metrics'
}
