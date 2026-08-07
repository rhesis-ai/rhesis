import { UUID } from 'crypto';

export interface TopicBase {
  name: string;
}

export type TopicCreate = TopicBase;

export type TopicUpdate = Partial<TopicBase>;

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
