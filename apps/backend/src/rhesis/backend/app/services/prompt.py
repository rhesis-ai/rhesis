import csv
import uuid
from io import StringIO
from typing import List

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app.models import Prompt, TestSet, Test
from rhesis.backend.app.models.test import test_test_set_association


def get_prompts_for_test_set(db: Session, test_set_id: uuid.UUID) -> List[dict]:
    # First check if test set exists
    test_set_exists = db.query(TestSet).filter(TestSet.id == test_set_id).first()
    if not test_set_exists:
        raise ValueError("Test Set not found")

    # Query both Test and Prompt data with joins to get the metadata from Test
    results = (
        db.query(Prompt, Test)
        .join(Test, Test.prompt_id == Prompt.id)
        .join(test_test_set_association, test_test_set_association.c.test_id == Test.id)
        .filter(test_test_set_association.c.test_set_id == test_set_id)
        .options(
            # Load Prompt relationships
            joinedload(Prompt.demographic),
            joinedload(Prompt.attack_category),
            joinedload(Prompt.source),
            joinedload(Prompt.status),
            # Load Test relationships for category, topic, behavior
            joinedload(Test.category),
            joinedload(Test.topic),
            joinedload(Test.behavior),
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
            prompts_data.append({
                "content": prompt.content,
                "demographic": prompt.demographic.name if prompt.demographic else None,
                "category": test.category.name if test.category else None,  # From Test
                "attack_category": prompt.attack_category.name if prompt.attack_category else None,
                "topic": test.topic.name if test.topic else None,  # From Test
                "language_code": prompt.language_code,
                "behavior": test.behavior.name if test.behavior else None,  # From Test
                "expected_response": prompt.expected_response,
                "source": prompt.source.title if prompt.source else None,
                "status": prompt.status.name if prompt.status else None,
            })
    
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
