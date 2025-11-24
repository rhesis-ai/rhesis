import { Status } from './status';

export interface Endpoint {
  id: string;
  name: string;
  description?: string;
  connection_type: 'REST' | 'WEBSOCKET' | 'GRPC' | 'SDK';
  url?: string;
  auth?: Record<string, any>;
  environment: 'development' | 'staging' | 'production';

  // Configuration Source
  config_source: 'manual' | 'openapi' | 'llm_generated' | 'sdk';
  openapi_spec_url?: string;
  openapi_spec?: Record<string, any>;
  llm_suggestions?: Record<string, any>;
  endpoint_metadata?: Record<string, any>;

  // Request Structure
  method?: string;
  endpoint_path?: string;
  request_headers?: Record<string, string>;
  query_params?: Record<string, any>;
  request_mapping?: Record<string, any>;
  input_mappings?: Record<string, any>;

  // Response Handling
  response_format: 'json' | 'xml' | 'text';
  response_mapping?: Record<string, string>;
  validation_rules?: Record<string, any>;

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
