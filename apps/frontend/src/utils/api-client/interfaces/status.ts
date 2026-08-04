import { UUID } from 'crypto';

export interface Status {
  id: UUID;
  name: string;
  description?: string;
  entity_type: string;
}

export interface StatusesQueryParams {
  skip?: number;
  limit?: number;
  entity_type?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
}
