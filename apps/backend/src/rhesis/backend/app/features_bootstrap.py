"""Register core features with the :class:`FeatureRegistry`.

Called once at application startup from ``main.py``. This is the single
declarative list of gated capabilities shipped with the open core.

To add a new feature:

1. Add a member to :class:`~rhesis.backend.app.features.FeatureName`.
2. Register it here with its ``runtime_check`` and ``min_plan``.
3. Guard server-side code via ``FeatureRegistry.is_available`` or the
   ``require_feature`` / ``has_feature`` FastAPI dependencies.
4. Mirror the name in ``apps/frontend/src/constants/features.ts`` and
   wrap the UI in ``<FeatureGate feature={FeatureName.X}>``.
"""

from __future__ import annotations

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.models.subscription import SubscriptionPlan


def _sso_runtime_check() -> bool:
    """Re-import ``is_sso_encryption_available`` on every call.

    Re-resolving the function from its canonical module makes the
    runtime check naturally mockable: tests can
    ``patch("rhesis.backend.app.utils.encryption.is_sso_encryption_available")``
    and the patch takes effect here without needing to reach into
    registry internals.
    """
    from rhesis.backend.app.utils.encryption import is_sso_encryption_available

    return is_sso_encryption_available()


def register_core_features() -> None:
    """Register all built-in features. Idempotent."""
    FeatureRegistry.register(
        Feature(
            name=FeatureName.SSO,
            display_name="Single Sign-On",
            min_plan=SubscriptionPlan.PREMIUM,
            runtime_check=_sso_runtime_check,
            description="Per-organization OIDC-based SSO.",
        )
    )


__all__ = ["register_core_features"]
