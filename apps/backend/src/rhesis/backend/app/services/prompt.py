import csv
import uuid
from io import StringIO
from typing import List

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app.models import Prompt, TestSet


def get_prompts_for_test_set(db: Session, test_set_id: uuid.UUID) -> List[dict]:
    test_set = (
        db.query(TestSet)
        .filter(TestSet.id == test_set_id)
        .options(
            joinedload(TestSet.prompts).joinedload(Prompt.demographic),
            joinedload(TestSet.prompts).joinedload(Prompt.category),
            joinedload(TestSet.prompts).joinedload(Prompt.attack_category),
            joinedload(TestSet.prompts).joinedload(Prompt.topic),
            joinedload(TestSet.prompts).joinedload(Prompt.behavior),
            joinedload(TestSet.prompts).joinedload(Prompt.source),
            joinedload(TestSet.prompts).joinedload(Prompt.status),
        )
        .first()
    )

    if not test_set:
        raise ValueError("Test Set not found")

    return [
        {
            "content": prompt.content,
            "demographic": prompt.demographic.name if prompt.demographic else None,
            "category": prompt.category.name if prompt.category else None,
            "attack_category": prompt.attack_category.name if prompt.attack_category else None,
            "topic": prompt.topic.name if prompt.topic else None,
            "language_code": prompt.language_code,
            "behavior": prompt.behavior.name if prompt.behavior else None,
            "expected_response": prompt.expected_response,
            "source": prompt.source.title if prompt.source else None,
            "status": prompt.status.name if prompt.status else None,
        }
        for prompt in test_set.prompts
    ]


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
