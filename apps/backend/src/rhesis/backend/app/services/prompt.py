import csv
import uuid
from io import StringIO
from typing import List

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app.models import Prompt, Test, TestSet
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.utils.crud_utils import get_item_detail


def get_prompts_for_test_set(
    db: Session, test_set_id: uuid.UUID, organization_id: str = None
) -> List[dict]:
    # First check if test set exists AND belongs to organization (SECURITY CRITICAL).
    # Raises ItemDeletedException for a soft-deleted test set; the sole caller
    # (download_test_set_prompts) already lets that through to its 410 response.
    test_set_exists = get_item_detail(db, TestSet, test_set_id, organization_id=organization_id)
    if not test_set_exists:
        raise ValueError("Test Set not found or not accessible")

    # Query both Test and Prompt data with joins to get the metadata from Test
    results_query = (
        db.query(Prompt, Test)
        .join(Test, Test.prompt_id == Prompt.id)
        .join(test_test_set_association, test_test_set_association.c.test_id == Test.id)
        .filter(test_test_set_association.c.test_set_id == test_set_id)
    )

    # Apply organization filtering to ensure data isolation (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID

        org_uuid = UUID(organization_id)
        results_query = results_query.filter(
            Test.organization_id == org_uuid, Prompt.organization_id == org_uuid
        )

    results = (
        results_query.options(
            # Load Prompt relationships
            # joinedload(Prompt.source),  # Temporarily disabled due to entity_type column issue
            joinedload(Prompt.status),
            # Load Test relationships for category, topic, requirement
            joinedload(Test.category),
            joinedload(Test.topic),
            joinedload(Test.requirement),
        )
        .distinct()
        .all()
    )

    # Process results and avoid duplicates based on prompt ID
    seen_prompts = set()
    prompts_data = []

    for prompt, test in results:
        if prompt.id not in seen_prompts:
            seen_prompts.add(prompt.id)
            prompts_data.append(
                {
                    "content": prompt.content,
                    "category": test.category.name if test.category else None,  # From Test
                    "topic": test.topic.name if test.topic else None,  # From Test
                    "language_code": prompt.language_code,
                    "requirement": test.requirement.name if test.requirement else None,  # From Test
                    "expected_response": prompt.expected_response,
                    "source": prompt.source.title if prompt.source else None,
                    "status": prompt.status.name if prompt.status else None,
                }
            )

    return prompts_data


def prompts_to_csv(prompts):
    if not prompts:
        raise ValueError("No prompts found in test set")

    output = StringIO()
    writer = csv.writer(output)

    fields = list(prompts[0].keys())

    # Write headers
    writer.writerow(fields)

    # Write prompt data
    for prompt in prompts:
        writer.writerow(prompt[field] for field in fields)

    output.seek(0)
    return output.getvalue()
