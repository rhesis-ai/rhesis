import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { User } from './user';
import { Tag } from './tag';
import { MetricScope } from './metric';
import { Model } from './model';

export interface BehaviorBase {
  name: string;
  description?: string | null;
  status_id?: UUID | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
}

export type BehaviorCreate = BehaviorBase;

export type BehaviorUpdate = Partial<BehaviorBase>;

export interface Behavior extends BehaviorBase {
  id: UUID;
  nano_id?: string | null;
  user?: User | null;
  metrics?: MetricWithRelationships[]; // Optional metrics when using include=metrics
  tags?: Tag[];
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

export interface BehaviorWithMetrics extends BehaviorBase {
  id: UUID;
  nano_id?: string | null;
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id: UUID;
  status_id: UUID;
  created_at?: string | null;
  status?: Status | null;
  user?: User | null;
  organization: Organization;
  metrics: MetricWithRelationships[]; // Full metric objects with type relationships
  tags?: Tag[];
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
  model?: Model | null;
}

export interface BehaviorsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
  include?: string;
}
