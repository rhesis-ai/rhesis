"""Scope onboarding demo data to the example project

Onboarding seeds behaviors, metrics, tests, and related demo content with
project_id NULL, which makes them visible in every project. Assign those rows
to the existing "Example Project (Insurance Chatbot)" per organization.

Revision ID: b3c4d5e6f7a8
Revises: c0d1e2f3a4b5
Create Date: 2026-07-02
"""

import json
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXAMPLE_PROJECT_NAME = "Example Project (Insurance Chatbot)"

# Shared reference data — keep project_id NULL (Status, TypeLookup, Model).
_ORG_WIDE_MODELS = frozenset({"Status", "TypeLookup", "Project", "Model"})


def _load_initial_data() -> dict:
    services_dir = os.path.join(os.path.dirname(__file__), "..", "..", "app", "services")
    path = os.path.join(services_dir, "initial_data.json")
    with open(path, "r") as file:
        return json.load(file)


def _get_model_name(key: str) -> str:
    if key == "status":
        return "Status"
    model_name = key.lower()
    if model_name.endswith("s"):
        model_name = model_name[:-1]
    return "".join(word.capitalize() for word in model_name.split("_"))


def _get_entity_identifier(model_name: str, item: dict) -> str | None:
    if model_name == "Test":
        return item.get("prompt")
    if model_name == "TypeLookup":
        return item.get("type_value")
    if model_name == "Prompt":
        return item.get("content") or item.get("prompt")
    if "name" in item:
        return item["name"]
    if "content" in item:
        return item["content"]
    return None


def _build_model_data_map(initial_data: dict) -> dict[str, set[str]]:
    model_data_map: dict[str, set[str]] = {}

    for key, items in initial_data.items():
        model_name = _get_model_name(key)
        identifiers = {
            ident for item in items if (ident := _get_entity_identifier(model_name, item))
        }
        if identifiers:
            model_data_map[model_name] = identifiers

    if "test_set" in initial_data:
        prompts: set[str] = set()
        topics: set[str] = set()
        behaviors: set[str] = set()
        categories: set[str] = set()

        for test_set in initial_data["test_set"]:
            for test in test_set.get("tests", []):
                if "prompt" in test:
                    prompts.add(test["prompt"])
                if "topic" in test:
                    topics.add(test["topic"])
                if "behavior" in test:
                    behaviors.add(test["behavior"])
                if "category" in test:
                    categories.add(test["category"])

        if prompts:
            model_data_map["Test"] = prompts
            model_data_map["Prompt"] = prompts
        if topics:
            model_data_map.setdefault("Topic", set()).update(topics)
        if behaviors:
            model_data_map.setdefault("Behavior", set()).update(behaviors)
        if categories:
            model_data_map.setdefault("Category", set()).update(categories)

    return model_data_map


def _table_for_model(model_name: str) -> str | None:
    mapping = {
        "Behavior": "behavior",
        "UseCase": "use_case",
        "Risk": "risk",
        "Category": "category",
        "Dimension": "dimension",
        "Demographic": "demographic",
        "Topic": "topic",
        "Test": "test",
        "TestSet": "test_set",
        "Metric": "metric",
        "Endpoint": "endpoint",
        "Prompt": "prompt",
    }
    return mapping.get(model_name)


def _fetch_example_projects(conn) -> list:
    conn.execute(sa.text("ALTER TABLE project DISABLE ROW LEVEL SECURITY"))
    projects = conn.execute(
        sa.text(
            """
            SELECT id, organization_id
            FROM project
            WHERE name = :name
              AND (deleted_at IS NULL OR deleted_at > now())
            """
        ),
        {"name": EXAMPLE_PROJECT_NAME},
    ).fetchall()
    conn.execute(sa.text("ALTER TABLE project ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE project FORCE ROW LEVEL SECURITY"))
    return projects


def upgrade() -> None:
    conn = op.get_bind()
    initial_data = _load_initial_data()
    model_data_map = _build_model_data_map(initial_data)

    projects = _fetch_example_projects(conn)

    if not projects:
        return

    for model_name, identifiers in model_data_map.items():
        if model_name in _ORG_WIDE_MODELS or not identifiers:
            continue

        table = _table_for_model(model_name)
        if table is None:
            continue

        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

        if model_name == "Test":
            conn.execute(sa.text("ALTER TABLE prompt DISABLE ROW LEVEL SECURITY"))
            for project_id, organization_id in projects:
                conn.execute(
                    sa.text(
                        """
                        UPDATE test t
                        SET project_id = :project_id
                        FROM prompt pr
                        WHERE t.prompt_id = pr.id
                          AND t.organization_id = :organization_id
                          AND t.project_id IS NULL
                          AND pr.content = ANY(:identifiers)
                        """
                    ),
                    {
                        "project_id": project_id,
                        "organization_id": organization_id,
                        "identifiers": list(identifiers),
                    },
                )
            conn.execute(sa.text("ALTER TABLE prompt ENABLE ROW LEVEL SECURITY"))
            conn.execute(sa.text("ALTER TABLE prompt FORCE ROW LEVEL SECURITY"))
        elif model_name == "Prompt":
            for project_id, organization_id in projects:
                conn.execute(
                    sa.text(
                        """
                        UPDATE prompt
                        SET project_id = :project_id
                        WHERE organization_id = :organization_id
                          AND project_id IS NULL
                          AND content = ANY(:identifiers)
                        """
                    ),
                    {
                        "project_id": project_id,
                        "organization_id": organization_id,
                        "identifiers": list(identifiers),
                    },
                )
        else:
            for project_id, organization_id in projects:
                conn.execute(
                    sa.text(
                        f"""
                        UPDATE {table}
                        SET project_id = :project_id
                        WHERE organization_id = :organization_id
                          AND project_id IS NULL
                          AND name = ANY(:identifiers)
                        """
                    ),
                    {
                        "project_id": project_id,
                        "organization_id": organization_id,
                        "identifiers": list(identifiers),
                    },
                )

        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


def downgrade() -> None:
    conn = op.get_bind()
    initial_data = _load_initial_data()
    model_data_map = _build_model_data_map(initial_data)

    projects = _fetch_example_projects(conn)

    if not projects:
        return

    for model_name, identifiers in model_data_map.items():
        if model_name in _ORG_WIDE_MODELS or not identifiers:
            continue

        table = _table_for_model(model_name)
        if table is None:
            continue

        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

        if model_name == "Test":
            conn.execute(sa.text("ALTER TABLE prompt DISABLE ROW LEVEL SECURITY"))
            for project_id, organization_id in projects:
                conn.execute(
                    sa.text(
                        """
                        UPDATE test t
                        SET project_id = NULL
                        FROM prompt pr
                        WHERE t.prompt_id = pr.id
                          AND t.organization_id = :organization_id
                          AND t.project_id = :project_id
                          AND pr.content = ANY(:identifiers)
                        """
                    ),
                    {
                        "project_id": project_id,
                        "organization_id": organization_id,
                        "identifiers": list(identifiers),
                    },
                )
            conn.execute(sa.text("ALTER TABLE prompt ENABLE ROW LEVEL SECURITY"))
            conn.execute(sa.text("ALTER TABLE prompt FORCE ROW LEVEL SECURITY"))
        elif model_name == "Prompt":
            for project_id, organization_id in projects:
                conn.execute(
                    sa.text(
                        """
                        UPDATE prompt
                        SET project_id = NULL
                        WHERE organization_id = :organization_id
                          AND project_id = :project_id
                          AND content = ANY(:identifiers)
                        """
                    ),
                    {
                        "project_id": project_id,
                        "organization_id": organization_id,
                        "identifiers": list(identifiers),
                    },
                )
        else:
            for project_id, organization_id in projects:
                conn.execute(
                    sa.text(
                        f"""
                        UPDATE {table}
                        SET project_id = NULL
                        WHERE organization_id = :organization_id
                          AND project_id = :project_id
                          AND name = ANY(:identifiers)
                        """
                    ),
                    {
                        "project_id": project_id,
                        "organization_id": organization_id,
                        "identifiers": list(identifiers),
                    },
                )

        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
