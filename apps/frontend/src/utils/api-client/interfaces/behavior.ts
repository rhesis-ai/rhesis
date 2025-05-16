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
}

export interface BehaviorsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: string;
  $filter?: string;
} 