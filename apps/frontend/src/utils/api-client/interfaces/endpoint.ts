export interface Endpoint {
  id: string;
  name: string;
  description?: string;
  protocol: 'REST' | 'WEBSOCKET' | 'GRPC';
  url: string;
  auth?: Record<string, any>;
  environment: 'development' | 'staging' | 'production';

  // Configuration Source
  config_source: 'manual' | 'openapi' | 'llm_generated';
  openapi_spec_url?: string;
  openapi_spec?: Record<string, any>;
  llm_suggestions?: Record<string, any>;

  // Request Structure
  method?: string;
  endpoint_path?: string;
  request_headers?: Record<string, string>;
  query_params?: Record<string, any>;
  request_body_template?: Record<string, any>;
  input_mappings?: Record<string, any>;

  // Response Handling
  response_format: 'json' | 'xml' | 'text';
  response_mappings?: Record<string, string>;
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

  // Note: auth_token, client_secret, last_token are write-only fields
  // They can be set during create/update but are never returned in responses
}

// Type for editing endpoints - includes write-only fields
export interface EndpointEditData extends Partial<Endpoint> {
  auth_token?: string;
  client_secret?: string;
}
