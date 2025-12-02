from enum import Enum


class EndpointConnectionType(str, Enum):
    REST = "REST"
    WEBSOCKET = "WebSocket"
    GRPC = "GRPC"
    SDK = "SDK"


class EndpointConfigSource(str, Enum):
    MANUAL = "manual"
    OPENAPI = "openapi"
    LLM_GENERATED = "llm_generated"
    SDK = "sdk"


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
