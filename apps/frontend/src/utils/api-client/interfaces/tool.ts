import { UUID } from 'crypto';

export interface TypeLookup {
  id: UUID;
  type_name: string;
  type_value: string;
  description?: string;
}

export interface Status {
  id: UUID;
  name: string;
  description?: string;
}

export interface User {
  id: UUID;
  name: string;
  email: string;
}

/** Known fields in tool_metadata - extensible via index signature */
export interface ToolMetadata {
  repository?: {
    full_name?: string;
    owner?: string;
    repo?: string;
    [key: string]: unknown;
  };
  space_key?: string;
  [key: string]: unknown;
}

export interface Tool {
  id: UUID;
  created_at: string;
  updated_at: string;
  name: string;
  description?: string;
  tool_type_id: UUID;
  tool_provider_type_id: UUID;
  status_id?: UUID;
  tool_metadata?: ToolMetadata;
  organization_id?: UUID;
  user_id?: UUID;

  // Relationships
  tool_type?: TypeLookup;
  tool_provider_type?: TypeLookup;
  status?: Status;
  user?: User;
}

export interface ToolCreate {
  name: string;
  description?: string;
  tool_type_id: UUID;
  tool_provider_type_id: UUID;
  status_id?: UUID;
  credentials: Record<string, unknown>;
  tool_metadata?: ToolMetadata;
  organization_id?: UUID;
  user_id?: UUID;
}

export interface ToolUpdate {
  name?: string;
  description?: string;
  tool_type_id?: UUID;
  tool_provider_type_id?: UUID;
  status_id?: UUID;
  credentials?: Record<string, unknown>;
  tool_metadata?: ToolMetadata;
  organization_id?: UUID;
  user_id?: UUID;
}

export interface ToolsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
}
