import { UUID } from 'crypto';

export interface TopicBase {
  name: string;
  description?: string | null;
  status_id?: UUID | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
}

export interface TopicCreate extends TopicBase {}

export interface TopicUpdate extends Partial<TopicBase> {}

export interface Topic extends TopicBase {
  id: UUID;
}

export interface TopicsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: string;
  $filter?: string;
  entity_type?: string;
} 