# Endpoint Configuration Guide

This guide explains how to configure endpoints in the system for both REST and WebSocket protocols, including authentication methods.

## Reserved Placeholders

The system uses special placeholders that are automatically replaced with actual values during request execution. These placeholders must be wrapped in double curly braces: `{{ placeholder }}`.

### Available Placeholders
- `{{ input }}`: The main input/query from the user
- `{{ auth_token }}`: The current authentication token (used in both bearer token and client credentials auth)
- `{{ session_id }}`: Unique session identifier

⚠️ **Important Notes**:
- Placeholders are case-sensitive
- Do not modify the placeholder names as they are reserved by the system
- Always use double curly braces syntax
- Placeholders cannot be nested

## Core Configuration Fields

### Basic Information
- `name`: A descriptive name for the endpoint (e.g., "Scavenger NL-to-SQL")
- `description`: Detailed description of the endpoint's purpose
- `url`: Full URL of the endpoint
  - REST: Starts with `https://` or `http://`
  - WebSocket: Starts with `wss://` or `ws://`
- `protocol`: Either "REST" or "WebSocket"
- `method`: 
  - REST: Standard HTTP methods ("GET", "POST", "PUT", "DELETE", etc.)
  - WebSocket: Use "WS"
- `endpoint_path`: The specific path portion of the URL (e.g., "/api/v1/query" or "/chat_ws")

### Request Configuration Fields

#### Common Fields
- `request_body_template`: String containing the JSON template for the request body
- `request_headers`: String containing the JSON template for request headers
- `query_params`: String containing URL query parameters (optional)

#### REST Example
```json
// request_body_template
{
  "query": "{{ input }}"
}

// request_headers
{
  "Content-Type": "application/json",
  "Authorization": "Bearer {{ auth_token }}"
}
```

#### WebSocket Example
```json
// request_body_template
{
  "auth_token": "{{ auth_token }}",
  "session_id": "{{ session_id }}",
  "query": "{{ input }}"
}

// request_headers
{
  "Upgrade": "websocket",
  "Connection": "Upgrade",
  "Sec-WebSocket-Version": "13"
}
```

### Response Configuration Fields

- `response_format`: Format of the response (e.g., "json")
- `response_mappings`: String containing JSON mapping of response fields

#### REST Example
```json
// response_mappings
{
  "output": "$.data.response"
}
```

#### WebSocket Example
```json
// response_mappings
{
  "conversation_id": "$.conversation_id",
  "error": "$.error",
  "status": "$.message"
}
```

### Authentication Fields

#### Bearer Token
- `auth_type`: "bearer"
- No additional fields required, uses `{{ auth_token }}` in headers

#### Client Credentials
- `auth_type`: "client_credentials"
- `client_id`: OAuth client ID
- `client_secret`: OAuth client secret
- `token_url`: OAuth token endpoint URL
- `scopes`: Array of required scopes
- `audience`: Target audience for the token (if required)

## Configuration Examples

### REST Endpoint
```json
{
  "name": "Data Query API",
  "description": "Endpoint for querying data using natural language",
  "url": "https://api.example.com/query",
  "protocol": "REST",
  "method": "POST",
  "endpoint_path": "/query",
  "request_body_template": "{\"query\": \"{{ input }}\"}",
  "request_headers": "{\"Authorization\": \"Bearer {{ auth_token }}\", \"Content-Type\": \"application/json\"}",
  "response_format": "json",
  "response_mappings": "{\"result\": \"$.data.result\"}",
  "auth_type": "bearer"
}
```

### WebSocket Endpoint
```json
{
  "name": "Real-time Chat API",
  "description": "WebSocket endpoint for real-time chat interactions",
  "url": "wss://api.example.com/chat",
  "protocol": "WebSocket",
  "method": "WS",
  "endpoint_path": "/chat",
  "request_body_template": "{\"auth_token\": \"{{ auth_token }}\", \"session_id\": \"{{ session_id }}\", \"query\": \"{{ input }}\"}",
  "request_headers": "{\"Upgrade\": \"websocket\", \"Connection\": \"Upgrade\", \"Sec-WebSocket-Version\": \"13\"}",
  "response_format": "json",
  "response_mappings": "{\"conversation_id\": \"$.conversation_id\", \"status\": \"$.message\"}",
  "auth_type": "client_credentials",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "token_url": "https://auth-provider.com/oauth/token",
  "scopes": ["chat:write"],
  "audience": "https://api.example.com"
}
```

## Best Practices

1. **Field Configuration**
   - Keep all JSON strings properly escaped
   - Store each configuration field separately
   - Validate JSON strings before saving
   - Use consistent formatting for readability

2. **Request Templates**
   - Keep templates as simple as possible
   - Include only required fields
   - Properly escape special characters
   - Validate placeholder syntax

3. **Response Mappings**
   - Use correct JSONPath syntax
   - Map all required response fields
   - Include error handling paths
   - Test mappings with sample responses

4. **Authentication**
   - Choose appropriate auth type
   - Secure credential storage
   - Implement proper token handling
   - Regular credential rotation

5. **WebSocket Specific**
   - Include required WebSocket headers
   - Handle connection lifecycle
   - Implement proper error handling
   - Monitor connection state

6. **Placeholder Usage**
   - Use only supported placeholders
   - Verify placeholder names exactly
   - Test placeholder replacement
   - Validate replaced values

## Validation Rules

You can specify validation rules for the endpoint using the `validation_rules` field:

```json
{
  "validation_rules": {
    "required_fields": ["input", "session_id"],
    "max_length": {
      "input": 1000
    },
    "format": {
      "session_id": "uuid"
    }
  }
}
```

## Troubleshooting

Common issues and their solutions:

1. **Authentication Failures**
   - Verify auth_type is correctly set
   - Check token expiration
   - Validate scopes configuration

2. **WebSocket Connection Issues**
   - Confirm WebSocket headers are present
   - Check SSL/TLS configuration
   - Verify proxy settings

3. **Response Mapping Errors**
   - Validate JSONPath expressions
   - Check response format matches expectation
   - Verify all required fields are mapped 