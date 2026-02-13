import { Status } from './status';

/** Known fields in endpoint_metadata - extensible via index signature */
export interface EndpointMetadata {
  sdk_connection?: {
    function_name?: string;
    [key: string]: unknown;
  };
  function_schema?: {
    description?: string;
    parameters?: Record<string, unknown>;
    [key: string]: unknown;
  };
  mapping_info?: {
    source?: string;
    confidence?: number;
    reasoning?: string;
    [key: string]: unknown;
  };
  validation_error?: {
    error?: string;
    reason?: string;
    [key: string]: unknown;
  };
  last_error?: string;
  created_at?: string;
  last_registered?: string;
  [key: string]: unknown;
}

export interface Endpoint {
  id: string;
  name: string;
  description?: string;
  connection_type: 'REST' | 'WEBSOCKET' | 'GRPC' | 'SDK';
  url?: string;
  auth?: Record<string, string | boolean | number>;
  environment: 'development' | 'staging' | 'production' | 'local';

  // Configuration Source
  config_source: 'manual' | 'openapi' | 'llm_generated' | 'sdk';
  openapi_spec_url?: string;
  openapi_spec?: Record<string, unknown>;
  llm_suggestions?: Record<string, unknown>;
  endpoint_metadata?: EndpointMetadata;

  // Request Structure
  method?: string;
  endpoint_path?: string;
  request_headers?: Record<string, string>;
  query_params?: Record<string, unknown>;
  request_mapping?: Record<string, unknown>;
  input_mappings?: Record<string, unknown>;

  // Response Handling
  response_format: 'json' | 'xml' | 'text';
  response_mapping?: Record<string, unknown>;
  validation_rules?: Record<string, unknown>;

  status_id?: string;
  user_id?: string;
  organization_id?: string;
  project_id?: string;

  // Nested project object (when included in response)
  project?: {
    id?: string;
    icon?: string;
    useCase?: string;
    name?: string;
  };

  // Nested status object (when included in response)
  status?: Status;

  // Note: auth_token, client_secret, last_token are write-only fields
  // They can be set during create/update but are never returned in responses
}

// Type for editing endpoints - includes write-only fields
export interface EndpointEditData extends Partial<Endpoint> {
  auth_token?: string;
  client_secret?: string;
}

// Type for testing endpoints without saving to database
export interface EndpointTestRequest {
  connection_type: 'REST' | 'WEBSOCKET' | 'GRPC' | 'SDK';
  url: string;
  method: string;
  request_headers: Record<string, string>;
  request_mapping: Record<string, unknown>;
  response_mapping: Record<string, string>;
  auth_type: 'bearer_token' | 'client_credentials';
  auth_token: string;
  input_data: Record<string, unknown>;
  endpoint_path?: string;
  query_params?: Record<string, unknown>;
  response_format?: 'json' | 'xml' | 'text';
}
