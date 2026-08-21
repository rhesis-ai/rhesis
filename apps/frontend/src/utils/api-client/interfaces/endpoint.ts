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
  environment: 'development' | 'staging' | 'production' | 'local';

  // Configuration Source
  config_source: 'manual' | 'openapi' | 'llm_generated' | 'sdk';
  endpoint_metadata?: EndpointMetadata;

  // Request Structure
  method?: string;
  endpoint_path?: string;
  request_headers?: Record<string, string>;
  request_mapping?: Record<string, unknown>;

  // Response Handling
  response_format: 'json' | 'xml' | 'text';
  response_mapping?: Record<string, unknown>;

  // Tracing control
  disable_tracing?: boolean;

  project_id?: string;
  organization_id?: string;

  created_at?: string;

  // Nested project object (when included in response)
  project?: {
    id?: string;
    name?: string;
  };

  // Nested status object (when included in response)
  status?: Status;

  // Nested user object (when included in the detail response)
  user?: {
    name?: string;
  };

  has_auth_token?: boolean;

  // Note: auth_token, client_secret, last_token are write-only fields
  // They can be set during create/update but are never returned in responses
}

// Type for editing endpoints - includes write-only fields.
// id/nano_id are assigned by the backend and ignored in request bodies, so they are
// omitted here to stop callers from spreading a fetched entity straight into an update.
export interface EndpointEditData extends Omit<
  Partial<Endpoint>,
  'id' | 'nano_id'
> {
  // null clears the stored token; undefined leaves it untouched
  auth_token?: string | null;
  client_secret?: string;
}

// Type for auto-configure request
export interface AutoConfigureRequest {
  input_text: string;
  url?: string;
  auth_token?: string;
  method?: string;
  probe?: boolean;
}

// Type for auto-configure result
export interface AutoConfigureResult {
  status: 'success' | 'partial' | 'failed';
  request_mapping?: Record<string, unknown>;
  response_mapping?: Record<string, unknown>;
  request_headers?: Record<string, string>;
  url?: string;
  method: string;
  confidence: number;
  reasoning: string;
  warnings: string[];
  probe_response?: Record<string, unknown>;
  probe_success: boolean;
  probe_error?: string;
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
