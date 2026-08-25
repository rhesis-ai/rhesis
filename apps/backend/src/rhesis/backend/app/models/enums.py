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


class JobStatus(str, Enum):
    """Lifecycle of a background job.

    Distinct from :class:`~rhesis.backend.jobs.enums.RunStatus`, which
    describes a *test run* and carries states (``Partial``) that make no sense
    for a job in general.

    ``CANCELLING`` is a request the job has not acknowledged yet. Celery's
    ``revoke`` only stops a job that has not started, and the workers run a
    thread pool where ``terminate=True`` would signal the whole process, so
    stopping a running job means the job itself noticing the request at a
    checkpoint and exiting. Until it does, the job is still running.
    """

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def terminal(cls) -> frozenset["JobStatus"]:
        """States a job never leaves."""
        return frozenset({cls.COMPLETED, cls.FAILED, cls.CANCELLED})

    @property
    def is_terminal(self) -> bool:
        return self in self.terminal()


class NotificationSection(str, Enum):
    """Sidebar section a notification's badge count belongs to.

    Values must equal the frontend NavigationPageItem.segment for that page,
    when the section badges a nav item at all (mirrored in
    src/constants/notifications.ts, kept in sync manually like
    FeatureName/Capability). ``USAGE`` badges nothing -- there is no
    "/usage" nav segment to attach a count to -- it exists so a quota
    notification still groups and displays in the notification drawer.
    """

    TEST_SETS = "test-sets"
    TEST_RUNS = "test-runs"
    TASKS = "tasks"
    ARCHITECT = "architect"
    USAGE = "usage"


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

    class Task(str, Enum):
        ASSIGNED = "task.assigned"

    class Architect(str, Enum):
        #: One architect turn concluded a background wait with nothing left
        #: pending -- i.e. the plan is done. Mid-plan turns don't notify; see
        #: the renderer in services/notification/catalog.py.
        PLAN_COMPLETED = "architect.plan_completed"

    class Usage(str, Enum):
        #: Crossed 80% of a resource's limit. Nothing is blocked yet.
        APPROACHING_LIMIT = "usage.approaching_limit"
        #: Crossed the resource's ceiling -- the action it gates is now
        #: blocked (a 402 on the next attempt).
        BLOCKED = "usage.blocked"


# Notification.entity_type reuses rhesis.backend.app.constants.EntityType
# (the same enum Comment.entity_type is typed with) rather than a new enum —
# it already carries TEST_SET / TEST_RUN.
