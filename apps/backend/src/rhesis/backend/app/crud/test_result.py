"""CRUD operations for test results.

``_TEST_RESULT_RELATED_FIELDS`` is what ``TestResultDetail`` serializes -- the test run
(scoped to the four columns ``TestRunReference`` actually reads: the full row also carries
``attributes``, which holds the run's ``metric_plan`` snapshot, one entry per test x metric,
so joining it unscoped costs O(tests^2) bytes on a list query), the test, and the test's
prompt and requirement. All many-to-one, so eager-loading them in one query costs nothing;
without them a results list issues four queries per row.

``_TEST_RESULT_DERIVED_FIELDS`` eager-loads exactly the comments/tasks/tags
``TestResultDetail`` actually serializes: its own (``CountsMixin``/``TagsMixin``), plus
``test.prompt``'s and ``test.requirement``'s (``PromptReference``/``RequirementReference``
both carry ``counts``/``tags`` too). ``QueryBuilder.with_default_derived_field_loads()`` looks
like the right tool here, but it only cascades one hop from the root model -- prompt and
requirement sit two hops down (via ``test``), so it never reaches them, and every row's prompt
and requirement lazy-load these individually (prompts are ~1:1 with tests, so this is what
made a results list scale O(tests) queries). The same auto-cascade also walks every one-hop
many-to-one relation of ``TestResult`` looking for mixin targets and happens to land on
``organization`` and ``project`` too -- neither of which ``TestResultDetail`` serializes at
all -- joining both in and eager-loading their tags for nothing. Listing exactly what's used
avoids both problems.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

_TEST_RESULT_RELATED_FIELDS = (
    include(
        models.TestResult.test_run,
        cols=[
            models.TestRun.id,
            models.TestRun.nano_id,
            models.TestRun.project_id,
            models.TestRun.name,
        ],
    ),
    include(models.TestResult.test),
    include(models.TestResult.test, models.Test.prompt),
    include(models.TestResult.test, models.Test.requirement),
)

_TEST_RESULT_DERIVED_FIELDS = (
    include(models.TestResult.comments),
    include(models.TestResult.tasks),
    include(models.TestResult.files),
    include(models.TestResult._tags_relationship, models.TaggedItem.tag),
    include(models.TestResult.test, models.Test.prompt, models.Prompt.comments),
    include(models.TestResult.test, models.Test.prompt, models.Prompt.tasks),
    include(
        models.TestResult.test,
        models.Test.prompt,
        models.Prompt._tags_relationship,
        models.TaggedItem.tag,
    ),
    include(models.TestResult.test, models.Test.requirement, models.Requirement.comments),
    include(models.TestResult.test, models.Test.requirement, models.Requirement.tasks),
    include(
        models.TestResult.test,
        models.Test.requirement,
        models.Requirement._tags_relationship,
        models.TaggedItem.tag,
    ),
)


def get_test_result(
    db: Session,
    test_result_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestResult]:
    """Get test_result with relationships (tags, test, test_run) eagerly loaded."""
    return get_item_detail(
        db,
        models.TestResult,
        test_result_id,
        organization_id=organization_id,
        user_id=user_id,
        related_fields=_TEST_RESULT_RELATED_FIELDS + _TEST_RESULT_DERIVED_FIELDS,
    )


def get_test_results(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
    strip_conversation: bool = False,
) -> List[models.TestResult]:
    """Get test_results with relationships (tags, test, test_run) eagerly loaded.

    ``strip_conversation=True`` drops ``test_output.conversation_summary`` from each row
    in memory before it's returned -- that's the full multi-turn transcript (every turn's
    reasoning, message, response, tool calls), useful to a caller rendering a conversation
    view but dead weight on a results grid that only reads ``goal_evaluation``/``status``/
    ``test_configuration.goal``. Expunges the rows from the session before
    mutating so the change can never be flushed back to the database.
    """
    results = (
        QueryBuilder(db, models.TestResult)
        .with_related(*_TEST_RESULT_RELATED_FIELDS, *_TEST_RESULT_DERIVED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )
    if strip_conversation:
        for result in results:
            db.expunge(result)
            if (
                isinstance(result.test_output, dict)
                and "conversation_summary" in result.test_output
            ):
                result.test_output = {
                    k: v for k, v in result.test_output.items() if k != "conversation_summary"
                }
    return results


def create_test_result(
    db: Session,
    test_result: schemas.TestResultCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.TestResult:
    """Create test_result."""
    return create_item(db, models.TestResult, test_result, organization_id, user_id)


def update_test_result(
    db: Session,
    test_result_id: uuid.UUID,
    test_result: schemas.TestResultUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestResult]:
    """Update test_result."""
    return update_item(db, models.TestResult, test_result_id, test_result, organization_id, user_id)


def delete_test_result(
    db: Session, test_result_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TestResult]:
    return delete_item(
        db, models.TestResult, test_result_id, organization_id=organization_id, user_id=user_id
    )
