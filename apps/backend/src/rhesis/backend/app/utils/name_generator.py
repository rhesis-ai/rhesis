import json
import os
import random
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


# Load data from JSON file
def _load_name_data():
    """Load adjectives and animals data from JSON file"""
    current_dir = os.path.dirname(__file__)
    json_path = os.path.join(current_dir, "name_generator_data.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["positive_adjectives"], data["animals"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        # Fallback to minimal lists if JSON file is not found or invalid
        print(f"Warning: Could not load name data from JSON: {e}")
        return (
            ["swift", "clever", "bright", "brave", "calm", "wise"],
            ["raven", "owl", "dolphin", "elephant", "fox", "wolf"],
        )


# Load the data once when module is imported
POSITIVE_ADJECTIVES, ANIMALS = _load_name_data()


def generate_memorable_name(db: Session, organization_id: UUID, max_attempts: int = 5) -> str:
    """
    Generate a unique memorable name for a test run using positive adjectives and animals.

    Args:
        db: Database session for uniqueness checking
        organization_id: Organization ID to scope uniqueness
        max_attempts: Maximum number of attempts to generate a unique name

    Returns:
        str: A unique memorable name like "swift-raven" or "creative-dolphin"
    """
    for attempt in range(max_attempts):
        # Generate random combination
        adjective = random.choice(POSITIVE_ADJECTIVES)
        animal = random.choice(ANIMALS)
        name = f"{adjective}-{animal}"

        # Check if name exists in organization
        if not _name_exists_in_organization(db, name, organization_id):
            return name

    # If we couldn't generate a unique name after max_attempts, add a number
    base_name = f"{random.choice(POSITIVE_ADJECTIVES)}-{random.choice(ANIMALS)}"
    counter = 1

    while _name_exists_in_organization(db, f"{base_name}-{counter}", organization_id):
        counter += 1
        if counter > 100:  # Prevent infinite loop
            # Fallback to timestamp-based name
            import time

            timestamp_suffix = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
            return f"{base_name}-{timestamp_suffix}"

    return f"{base_name}-{counter}"


def _name_exists_in_organization(db: Session, name: str, organization_id: UUID) -> bool:
    """
    Check if a test run name already exists within the organization.

    Args:
        db: Database session
        name: Name to check
        organization_id: Organization ID to scope the check

    Returns:
        bool: True if name exists, False otherwise
    """
    try:
        # Use raw SQL for efficient existence check
        result = db.execute(
            text("""
                SELECT EXISTS(
                    SELECT 1 FROM test_run 
                    WHERE name = :name 
                    AND organization_id = :org_id
                )
            """),
            {"name": name, "org_id": str(organization_id)},
        )
        return result.scalar()
    except Exception:
        # If there's any error, assume name exists to be safe
        return True
