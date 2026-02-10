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
    API_KEY = "api_key"
    # Add more as needed


class ModelType(str, Enum):
    """Type of AI model configuration."""

    LLM = "llm"
    EMBEDDING = "embedding"


class EmbeddingStatus(str, Enum):
    """
    Internal lifecycle status for embeddings.
    Not exposed to users - managed automatically by the system.
    """

    ACTIVE = "active"
    STALE = "stale"


class EmbeddingOrigin(str, Enum):
    """Origin/source of the embedded content"""

    USER = "user"
    GENERATED = "generated"
    IMPORTED = "imported"
