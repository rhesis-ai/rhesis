import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { User } from './user';
import { Tag } from './tag';
import { MetricScope } from './metric';

export interface RequirementBase {
  name: string;
  description?: string | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
}

export type RequirementCreate = RequirementBase;

export type RequirementUpdate = Partial<RequirementBase>;

export interface Requirement extends RequirementBase {
  id: UUID;
}

export interface RequirementReference {
  id: UUID;
  name: string;
  description?: string | null;
}

export interface RequirementWithMetrics extends RequirementBase {
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

/** id + name only -- what filter dropdowns and pickers need. */
export interface RequirementOption {
  id: UUID;
  name: string;
}

export interface RequirementsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
  /** Comma-separated fields to return; `id` is always included. */
  $select?: string;
  include?: string;
}
