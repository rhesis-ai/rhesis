"""OTLP/HTTP trace ingest for the OpenTelemetry GenAI semantic conventions.

Registers ``FeatureName.OTLP_INGEST``, the ``POST /telemetry/v1/traces`` route
(mounted by :func:`~rhesis.backend.ee.bootstrap`), and the worker step that joins
conversation turns arriving under separate trace ids.
"""

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.services.telemetry.ingest import register_pre_store_hook
from rhesis.backend.ee.otlp.conversation_join import PRE_STORE_HOOK, join_conversation_turns


def register_otlp_worker_hooks() -> None:
    """The worker-side step OTLP jobs name. Runs in the API and in every worker. Idempotent."""
    register_pre_store_hook(PRE_STORE_HOOK, join_conversation_turns)


def register_otlp_ingest() -> None:
    """Register the feature. Idempotent."""
    FeatureRegistry.register(
        Feature(
            name=FeatureName.OTLP_INGEST,
            display_name="OTLP trace ingest",
            description=(
                "Receive traces from any OpenTelemetry exporter (OTLP/HTTP) and "
                "translate the OpenTelemetry GenAI semantic conventions."
            ),
        )
    )
