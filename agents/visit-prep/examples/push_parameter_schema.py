"""Push Visit-Prep's experiment parameter slots to its Rhesis project.

Overwrites the project's parameter schema with the slots :mod:`visit_prep.config` reads, defaulted
to the values the code ships with. Run it again after adding a slot or editing a default prompt.

    uv run python examples/push_parameter_schema.py --dry-run
    uv run python examples/push_parameter_schema.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from rhesis.sdk import Parameters
from visit_prep.config import parameter_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("visit_prep.examples.push_parameter_schema")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Print the schema, push nothing.")
    args = parser.parse_args()

    schema = parameter_schema()
    if args.dry_run:
        print(json.dumps(schema.model_dump(mode="json"), indent=2))
        return 0

    project_id = os.getenv("RHESIS_PROJECT_ID")
    if not (project_id and os.getenv("RHESIS_API_KEY")):
        logger.error("Set RHESIS_API_KEY and RHESIS_PROJECT_ID (in .env or the environment).")
        return 1

    Parameters.put_schema(project_id=project_id, schema=schema)
    names = ", ".join(field.name for field in schema.fields)
    logger.info("Pushed %d slots to project %s: %s", len(schema.fields), project_id, names)
    return 0


if __name__ == "__main__":
    sys.exit(main())
