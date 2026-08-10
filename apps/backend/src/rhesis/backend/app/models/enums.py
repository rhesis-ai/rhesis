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

    LANGUAGE = "language"
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


class NotificationSection(str, Enum):
    """Sidebar section a notification's badge count belongs to.

    Values must equal the frontend NavigationPageItem.segment for that page
    (mirrored in src/constants/notifications.ts, kept in sync manually like
    FeatureName/Capability).
    """

    TEST_SETS = "test-sets"
    TEST_RUNS = "test-runs"


class NotificationEventType:
    """Namespace of notification event-kind identifiers, grouped by resource.

    Mirrors ``Permission``'s nested-enum grouping in ``auth/capabilities.py``
    (``Permission.TestSet.READ``) rather than one flat enum, so a resource
    with several event kinds reads as ``NotificationEventType.TestSet.X``
    instead of a repeated ``TEST_SET_`` prefix on every member.
    """

    class TestSet(str, Enum):
        GENERATION_COMPLETED = "test_set.generation_completed"
        GARAK_IMPORT_COMPLETED = "test_set.garak_import_completed"
        GARAK_SYNC_COMPLETED = "test_set.garak_sync_completed"

    class TestRun(str, Enum):
        EXECUTION_COMPLETED = "test_run.execution_completed"


# Notification.entity_type reuses rhesis.backend.app.constants.EntityType
# (the same enum Comment.entity_type is typed with) rather than a new enum —
# it already carries TEST_SET / TEST_RUN.
