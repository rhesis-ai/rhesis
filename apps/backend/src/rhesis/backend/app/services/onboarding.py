"""Seeded example rows never count. Project-scoped rows are checked per visible project under
``temporary_project_scope``."""

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app.crud.endpoint import user_endpoint_exists
from rhesis.backend.app.crud.project import list_visible_project_example_flags
from rhesis.backend.app.crud.test import user_test_exists
from rhesis.backend.app.crud.test_set import user_test_set_exists
from rhesis.backend.app.crud.user import other_org_member_exists
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.user import OnboardingStatus

# Empty project id means the org-level scope, where project_id IS NULL rows live.
_ORG_LEVEL_SCOPE = ""


def get_onboarding_status(db: Session, organization_id: str, user_id: str) -> OnboardingStatus:
    """Return which onboarding steps the caller's organization has really done."""
    projects = list_visible_project_example_flags(db, organization_id, user_id)
    endpoint_setup, test_cases_created = _scan_project_data(
        db, organization_id, user_id, [str(project_id) for project_id, _ in projects]
    )
    return OnboardingStatus(
        project_created=any(not is_example for _, is_example in projects),
        endpoint_setup=endpoint_setup,
        users_invited=other_org_member_exists(db, organization_id, user_id),
        test_cases_created=test_cases_created,
    )


def mark_profile_survey_pending(user: User) -> None:
    """Flag an invitee to be asked the profile questions; invitees never see /onboarding."""
    if user.job_role is not None:
        return
    user.settings.update({"onboarding": {"profile_survey_pending": True}})
    flag_modified(user, "user_settings")


def _scan_project_data(
    db: Session, organization_id: str, user_id: str, project_ids: list[str]
) -> tuple[bool, bool]:
    """Check each scope for a user-made endpoint and test, stopping once both are found."""
    endpoint_found = False
    tests_found = False
    for project_id in [_ORG_LEVEL_SCOPE, *project_ids]:
        with temporary_project_scope(db, organization_id, user_id, project_id):
            endpoint_found = endpoint_found or user_endpoint_exists(db, organization_id)
            tests_found = (
                tests_found
                or user_test_exists(db, organization_id)
                or user_test_set_exists(db, organization_id)
            )
        if endpoint_found and tests_found:
            break
    return endpoint_found, tests_found
