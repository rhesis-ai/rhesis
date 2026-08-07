import { UUID } from 'crypto';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { PaginationParams } from './pagination';

export interface Model {
  id: UUID;
  name: string;
  description?: string;
  icon?: string;
  model_name: string;
  model_type?: 'language' | 'embedding';
  endpoint: string;
  is_protected?: boolean;

  /**
   * Whether the model is currently usable. Defaults to true; the backend sets
   * it to false for Rhesis-hosted models when their prerequisite (e.g. a valid
   * platform key) is missing on a local deployment.
   */
  available?: boolean;
  /**
   * Machine slug explaining why the model is unavailable (e.g.
   * `rhesis_key_missing`, `polyphemus_not_authorized`), or null when available.
   * Human-readable copy lives in the frontend — see `AVAILABILITY_REASON_COPY`.
   */
  availability_reason?: string | null;

  // References
  provider_type?: TypeLookup;
  status?: Status;
}

export interface ModelCreate {
  name: string;
  description?: string;
  icon?: string;
  model_name: string;
  model_type?: 'language' | 'embedding';
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
  model_type?: 'language' | 'embedding';
  endpoint?: string;
  key?: string;
  is_protected?: boolean;
  tags?: string[];
  provider_type_id?: UUID;
  status_id?: UUID;
  owner_id?: UUID;
  assignee_id?: UUID;
}

export type ModelDetail = Model;

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
  model_type?: 'language' | 'embedding';
}

export interface TestModelConnectionResponse {
  success: boolean;
  message: string;
}
