import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { User } from './user';
import { Tag } from './tag';
import { MetricScope } from './metric';

export interface BehaviorBase {
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
}

export type BehaviorCreate = BehaviorBase;

export type BehaviorUpdate = Partial<BehaviorBase>;

export interface Behavior extends BehaviorBase {
  id: UUID;
}

export interface BehaviorReference {
  id: UUID;
  name: string;
  description?: string | null;
}

export interface BehaviorWithMetrics extends BehaviorBase {
  id: UUID;
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id: UUID;
  created_at?: string | null;
  user?: User | null;
  metrics: MetricWithRelationships[]; // Full metric objects with type relationships
  tags?: Tag[];
}

export interface MetricWithRelationships {
  id: UUID;
  name: string;
  description: string;
  score_type: string;
  metric_scope?: MetricScope[];

  // Required relationship objects (now always included from backend)
  metric_type: TypeLookup;
  backend_type: TypeLookup;

  // Optional relationship objects
  status?: Status | null;
}

export interface BehaviorsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
  include?: string;
}
