"""Per-user email notification preferences.

Live in-app notifications already cover every event that also sends an email,
so a user can switch the emails off. Each kind here maps to one toggle on the
Notifications tab of user settings; unset reads as on, so nobody loses an
email they were getting before the setting existed.
"""

import logging
from enum import Enum

from rhesis.backend.app import models

logger = logging.getLogger(__name__)


class EmailNotificationKind(str, Enum):
    """The email families a user can switch off.

    Values match the keys under ``user_settings.notifications.email`` and the
    properties on ``EmailNotificationSettingsAccessor``.
    """

    JOB_COMPLETION = "job_completion"
    TASK_ASSIGNMENT = "task_assignment"


def email_enabled(user: models.User, kind: EmailNotificationKind) -> bool:
    """Whether *user* still wants emails of this kind.

    Errs on the side of sending: a user row we can't read a preference off
    should still get their email rather than silently lose it.
    """
    try:
        return bool(getattr(user.settings.notifications.email, kind.value))
    except Exception as e:
        logger.warning(
            "Could not read email notification preference %s for user %s: %s",
            kind.value,
            getattr(user, "id", "unknown"),
            e,
        )
        return True
