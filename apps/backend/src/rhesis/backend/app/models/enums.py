from enum import Enum


class EndpointProtocol(str, Enum):
    REST = "REST"
    WEBSOCKET = "WebSocket"
    GRPC = "GRPC"


class EndpointConfigSource(str, Enum):
    MANUAL = "manual"
    OPENAPI = "openapi"
    LLM_GENERATED = "llm_generated"


class EndpointResponseFormat(str, Enum):
    JSON = "json"
    XML = "xml"
    TEXT = "text"


class EndpointEnvironment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    LOCAL = "local"


class EndpointAuthType(str, Enum):
    BEARER_TOKEN = "bearer_token"
    CLIENT_CREDENTIALS = "client_credentials"
    # Add more as needed
