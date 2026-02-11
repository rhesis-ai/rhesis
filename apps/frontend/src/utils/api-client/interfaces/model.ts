import { UUID } from 'crypto';
import { User } from './user';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { PaginationParams } from './pagination';

export interface Model {
  id: UUID;
  name: string;
  description?: string;
  icon?: string;
  model_name: string;
  model_type?: 'llm' | 'embedding';
  endpoint: string;
  key: string;
  is_protected?: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;

  // References
  provider_type?: TypeLookup;
  status?: Status;
  owner?: User;
  assignee?: User;
  metrics?: UUID[];
}

export interface ModelCreate {
  name: string;
  description?: string;
  icon?: string;
  model_name: string;
  model_type?: 'llm' | 'embedding';
  endpoint?: string;
  key: string;
  is_protected?: boolean;
  tags: string[];
  provider_type_id?: UUID;
  status_id?: UUID;
  owner_id?: UUID;
  assignee_id?: UUID;
}

export interface ModelUpdate {
  name?: string;
  description?: string;
  icon?: string;
  model_name?: string;
  model_type?: 'llm' | 'embedding';
  endpoint?: string;
  key?: string;
  is_protected?: boolean;
  tags?: string[];
  provider_type_id?: UUID;
  status_id?: UUID;
  owner_id?: UUID;
  assignee_id?: UUID;
}

export interface ModelDetail extends Model {
  metrics: UUID[];
}

export interface ModelsResponse {
  models: ModelDetail[];
  totalCount: number;
}

export interface ModelQueryParams extends PaginationParams {
  status?: string;
  provider_type?: string;
}

export interface TestModelConnectionRequest {
  provider: string;
  model_name: string;
  api_key?: string;
  model_id?: UUID;
  endpoint?: string;
  model_type?: 'llm' | 'embedding';
}

export interface TestModelConnectionResponse {
  success: boolean;
  message: string;
  provider?: string;
  model_name?: string;
}
