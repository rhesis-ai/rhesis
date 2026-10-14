"""Seeded example rows never count. Project-scoped rows are checked per visible project under
``temporary_project_scope``."""

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.endpoint import user_endpoint_exists
from rhesis.backend.app.crud.project import list_visible_project_example_flags
from rhesis.backend.app.crud.test_result import user_agent_test_result_exists
from rhesis.backend.app.crud.user import other_org_member_exists
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.schemas.user import OnboardingStatus

# Empty project id means the org-level scope, where project_id IS NULL rows live.
_ORG_LEVEL_SCOPE = ""


def get_onboarding_status(db: Session, organization_id: str, user_id: str) -> OnboardingStatus:
    """Return which onboarding steps the caller has really done."""
    projects = list_visible_project_example_flags(db, organization_id, user_id)
    endpoint_setup, agent_tested = _scan_project_data(
        db, organization_id, user_id, [str(project_id) for project_id, _ in projects]
    )
    return OnboardingStatus(
        endpoint_setup=endpoint_setup,
        agent_tested=agent_tested,
        users_invited=other_org_member_exists(db, organization_id, user_id),
    )


def _scan_project_data(
    db: Session, organization_id: str, user_id: str, project_ids: list[str]
) -> tuple[bool, bool]:
    """Check each scope for a user-made endpoint and test results against it, stopping once
    both are found."""
    endpoint_found = False
    results_found = False
    for project_id in [_ORG_LEVEL_SCOPE, *project_ids]:
        with temporary_project_scope(db, organization_id, user_id, project_id):
            endpoint_found = endpoint_found or user_endpoint_exists(db, organization_id)
            results_found = results_found or user_agent_test_result_exists(db, organization_id)
        if endpoint_found and results_found:
            break
    return endpoint_found, results_found
