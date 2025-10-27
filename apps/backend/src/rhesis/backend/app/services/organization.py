import json
import os
import uuid
from typing import List, Type

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.metric import behavior_metric_association
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_behavior,
    get_or_create_category,
    get_or_create_entity,
    get_or_create_status,
    get_or_create_topic,
    get_or_create_type_lookup,
)
from rhesis.backend.app.utils.model_utils import QueryBuilder


def load_initial_data(db: Session, organization_id: str, user_id: str) -> None:
    """
    Load initial data from the JSON file into the database using optimized approach.

    This function uses the provided database session to ensure transaction consistency
    with the calling code. The tenant context is passed directly to CRUD operations.

    Performance improvements:
    - Uses provided db session for transaction consistency
    - Eliminates manual session variable management
    - Direct tenant context injection

    Args:
        db: Database session to use for all operations
        organization_id: Organization ID to associate with all entities
        user_id: User ID to associate with all entities
    """
    script_directory = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_directory, "initial_data.json"), "r") as file:
        initial_data = json.load(file)

    try:
        # Use the provided database session for transaction consistency
        # Process type lookups first as they're needed by other entities
        print("Processing type lookups...")
        for item in initial_data.get("type_lookup", []):
            get_or_create_type_lookup(
                db=db,
                type_name=item["type_name"],
                type_value=item["type_value"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process statuses next as they're also needed by other entities
        print("Processing statuses...")
        for item in initial_data.get("status", []):
            get_or_create_status(
                db=db,
                name=item["name"],
                entity_type=item["entity_type"],
                description=item.get("description"),
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process behaviors
        print("Processing behaviors...")
        for item in initial_data.get("behavior", []):
            get_or_create_behavior(
                db=db,
                name=item["name"],
                description=item["description"],
                status=item.get("status"),
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process use cases
        print("Processing use cases...")
        for item in initial_data.get("use_case", []):
            # Extract only the fields that exist in the model
            use_case_data = {
                "name": item["name"],
                "description": item["description"],
                "industry": item.get("industry"),
                "application": item.get("application"),
                "is_active": item.get("is_active", True),
            }
            get_or_create_entity(
                db=db,
                model=models.UseCase,
                entity_data=use_case_data,
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process risks
        print("Processing risks...")
        for item in initial_data.get("risk", []):
            get_or_create_entity(
                db=db,
                model=models.Risk,
                entity_data={"name": item["name"], "description": item["description"]},
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process projects
        print("Processing projects...")
        for item in initial_data.get("project", []):
            # Get project status if specified
            status = None
            if item.get("status"):
                status = get_or_create_status(
                    db=db,
                    name=item["status"],
                    entity_type="General",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

            project_data = {
                "name": item["name"],
                "description": item["description"],
                "is_active": item.get("is_active", True),
                "icon": item.get("icon"),
                "user_id": user_id,  # Set the creating user
                "owner_id": user_id,  # Set the owner to the same user
            }

            if status:
                project_data["status_id"] = status.id

            get_or_create_entity(
                db=db,
                model=models.Project,
                entity_data=project_data,
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process categories
        print("Processing categories...")
        for item in initial_data.get("category", []):
            get_or_create_category(
                db=db,
                name=item["name"],
                description=item["description"],
                entity_type=item.get("entity_type"),
                status=item.get("status"),
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process dimensions
        print("Processing dimensions...")
        for item in initial_data.get("dimension", []):
            get_or_create_entity(
                db=db,
                model=models.Dimension,
                entity_data={"name": item["name"], "description": item["description"]},
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process demographics
        print("Processing demographics...")
        for item in initial_data.get("demographic", []):
            item_copy = item.copy()  # Don't modify original data
            dimension_name = item_copy.pop("dimension", None)
            demographic = get_or_create_entity(
                db=db,
                model=models.Demographic,
                entity_data=item_copy,
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )
            if dimension_name:
                dimension = (
                    db.query(models.Dimension)
                    .filter(
                        models.Dimension.name == dimension_name,
                        models.Dimension.organization_id == uuid.UUID(organization_id),
                    )
                    .first()
                )
                if dimension:
                    demographic.dimension_id = dimension.id
                    db.flush()

        # Process topics
        print("Processing topics...")
        for item in initial_data.get("topic", []):
            get_or_create_topic(
                db=db,
                name=item["name"],
                description=item["description"],
                entity_type=item.get("entity_type"),
                status=item.get("status"),
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process tests
        print("Processing tests...")
        created_tests = []
        for item in initial_data.get("test", []):
            # Get test type
            test_type = get_or_create_type_lookup(
                db=db,
                type_name="TestType",
                type_value=item["test_type"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get test status
            status = get_or_create_status(
                db=db,
                name=item["status"],
                entity_type="Test",
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get topic
            topic = get_or_create_topic(
                db=db,
                name=item["topic"],
                entity_type="Test",
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get category
            category = get_or_create_category(
                db=db,
                name=item["category"],
                entity_type="Test",
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get behavior
            behavior = get_or_create_behavior(
                db=db,
                name=item["behavior"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Create prompt
            prompt = get_or_create_entity(
                db=db,
                model=models.Prompt,
                entity_data={"content": item["prompt"]},
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Create test
            test = get_or_create_entity(
                db=db,
                model=models.Test,
                entity_data={
                    "prompt_id": prompt.id,
                    "test_type_id": test_type.id,
                    "status_id": status.id,
                    "topic_id": topic.id,
                    "category_id": category.id,
                    "behavior_id": behavior.id,
                    "priority": item.get("priority", 1),
                },
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )
            created_tests.append(test)

        # Process test sets
        print("Processing test sets...")
        created_test_sets = []
        for item in initial_data.get("test_set", []):
            # Get test set status
            status = get_or_create_status(
                db=db,
                name=item["status"],
                entity_type="TestSet",
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get license type
            license_type = get_or_create_type_lookup(
                db=db,
                type_name="LicenseType",
                type_value=item["license_type"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Create test set
            test_set = get_or_create_entity(
                db=db,
                model=models.TestSet,
                entity_data={
                    "name": item["name"],
                    "description": item["description"],
                    "short_description": item["short_description"],
                    "status_id": status.id,
                    "license_type_id": license_type.id,
                    "visibility": item["visibility"],
                    "attributes": item["metadata"],
                    "user_id": uuid.UUID(user_id),  # Set the creating user
                    "owner_id": uuid.UUID(user_id),  # Set the owner to the same user
                    "assignee_id": uuid.UUID(user_id),  # Set the assignee to the same user
                    "organization_id": uuid.UUID(organization_id),
                },
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Associate tests with test set
            for test in created_tests:
                # Get the actual test object from the database
                db_test = (
                    db.query(models.Test)
                    .filter(
                        models.Test.id == test.id,
                        models.Test.organization_id == uuid.UUID(organization_id),
                    )
                    .first()
                )

                if db_test:
                    values = {
                        "test_id": db_test.id,
                        "test_set_id": test_set.id,
                        "organization_id": uuid.UUID(organization_id),
                        "user_id": uuid.UUID(user_id),
                    }
                    db.execute(test_test_set_association.insert().values(**values))
                    db.flush()

            # Track test sets to update attributes after associations are complete
            created_test_sets.append(test_set)

        # Update test set attributes based on associated tests
        print("Updating test set attributes...")
        from rhesis.backend.app.services.test_set import update_test_set_attributes

        for test_set in created_test_sets:
            try:
                update_test_set_attributes(db=db, test_set_id=str(test_set.id))
            except Exception as e:
                print(f"Warning: Failed to update attributes for test set {test_set.name}: {e}")

        # Process endpoints
        print("Processing endpoints...")
        for item in initial_data.get("endpoint", []):
            # Get project if specified
            project = None
            if item.get("project"):
                project = (
                    db.query(models.Project)
                    .filter(
                        models.Project.name == item["project"],
                        models.Project.organization_id == uuid.UUID(organization_id),
                    )
                    .first()
                )

            # Get status if specified
            status = None
            if item.get("status"):
                status = get_or_create_status(
                    db=db,
                    name=item["status"],
                    entity_type="General",
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

            # Build endpoint data
            endpoint_data = {
                "name": item["name"],
                "description": item.get("description"),
                "protocol": item["protocol"],
                "url": item["url"],
                "method": item.get("method"),
                "environment": item.get("environment", "development"),
                "config_source": item.get("config_source", "manual"),
                "response_format": item.get("response_format", "json"),
                "request_headers": item.get("request_headers"),
                "request_body_template": item.get("request_body_template"),
                "response_mappings": item.get("response_mappings"),
                "query_params": item.get("query_params"),
                "validation_rules": item.get("validation_rules"),
            }

            # Add authentication fields if specified
            # Only set auth_type if we have a valid auth_token
            auth_token_loaded = False

            if item.get("auth_token"):
                # Replace environment variable placeholders (e.g., ${CHATBOT_API_KEY})
                auth_token = item["auth_token"]
                if auth_token.startswith("${") and auth_token.endswith("}"):
                    env_var_name = auth_token[2:-1]  # Extract variable name
                    auth_token = os.getenv(env_var_name)
                    if auth_token:
                        endpoint_data["auth_token"] = auth_token
                        auth_token_loaded = True
                        print(
                            f"  ✓ Loaded {env_var_name} from environment for endpoint: {item['name']}"
                        )
                    else:
                        print(
                            f"  ⚠ Warning: {env_var_name} not found in environment for endpoint: {item['name']}"
                        )
                        print("  → Skipping auth_type configuration (no token available)")
                else:
                    # Use the value directly if not a placeholder
                    endpoint_data["auth_token"] = auth_token
                    auth_token_loaded = True

            # Only set auth_type if we successfully loaded an auth_token
            if item.get("auth_type") and auth_token_loaded:
                endpoint_data["auth_type"] = item["auth_type"]

            # Add optional relationships
            if project:
                endpoint_data["project_id"] = project.id
            if status:
                endpoint_data["status_id"] = status.id

            get_or_create_entity(
                db=db,
                model=models.Endpoint,
                entity_data=endpoint_data,
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

        # Process metrics
        print("Processing metrics...")
        for item in initial_data.get("metric", []):
            # Get metric type
            metric_type = get_or_create_type_lookup(
                db=db,
                type_name="MetricType",
                type_value=item["metric_type"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get backend type
            backend_type = get_or_create_type_lookup(
                db=db,
                type_name="BackendType",
                type_value=item["backend_type"],
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Get metric status
            status = get_or_create_status(
                db=db,
                name=item["status"],
                entity_type="Metric",
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Create metric
            metric_data = {
                "name": item["name"],
                "description": item["description"],
                "evaluation_prompt": item["evaluation_prompt"],
                "evaluation_steps": item.get("evaluation_steps"),
                "reasoning": item.get("reasoning"),
                "score_type": item["score_type"],
                "min_score": item.get("min_score"),
                "max_score": item.get("max_score"),
                "threshold": item.get("threshold"),
                "explanation": item.get("explanation"),
                "ground_truth_required": item.get("ground_truth_required", False),
                "context_required": item.get("context_required", False),
                "class_name": item.get("class_name"),
                "evaluation_examples": item.get("evaluation_examples"),
                "threshold_operator": item.get("threshold_operator", ">="),
                "reference_score": item.get("reference_score"),
                "metric_type_id": metric_type.id,
                "backend_type_id": backend_type.id,
                "status_id": status.id,
                "user_id": uuid.UUID(user_id),
                "owner_id": uuid.UUID(user_id),
            }

            metric = get_or_create_entity(
                db=db,
                model=models.Metric,
                entity_data=metric_data,
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )

            # Process behavior associations
            behavior_names = item.get("behaviors", [])
            for behavior_name in behavior_names:
                # Get or create the behavior
                behavior = get_or_create_behavior(
                    db=db,
                    name=behavior_name,
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )

                # Check if association already exists
                existing_association = db.execute(
                    behavior_metric_association.select().where(
                        behavior_metric_association.c.behavior_id == behavior.id,
                        behavior_metric_association.c.metric_id == metric.id,
                    )
                ).first()

                # Create association if it doesn't exist
                if not existing_association:
                    association_values = {
                        "behavior_id": behavior.id,
                        "metric_id": metric.id,
                        "organization_id": uuid.UUID(organization_id),
                        "user_id": uuid.UUID(user_id),
                    }
                    db.execute(behavior_metric_association.insert().values(**association_values))
                    db.flush()

        # Process default Rhesis model
        print("Processing default Rhesis model...")
        # Get the Rhesis provider type
        rhesis_provider_type = get_or_create_type_lookup(
            db=db,
            type_name="ProviderType",
            type_value="rhesis",
            organization_id=organization_id,
            user_id=user_id,
            commit=False,
        )

        # Get Available status for the model
        available_status = get_or_create_status(
            db=db,
            name="Available",
            entity_type="Model",
            organization_id=organization_id,
            user_id=user_id,
            commit=False,
        )

        # Get the backend-configured model name (e.g., gemini-2.0-flash)
        from rhesis.backend.app.constants import DEFAULT_MODEL_NAME

        default_model_name = DEFAULT_MODEL_NAME

        # Create the default Rhesis model
        default_model_data = {
            "name": "Rhesis Default",
            "model_name": default_model_name,
            "description": "Default Rhesis-hosted model. No API key required.",
            "icon": "rhesis",  # Maps to PROVIDER_ICONS['rhesis'] in frontend
            "provider_type_id": rhesis_provider_type.id,
            "status_id": available_status.id,
            "key": "",  # Empty string for system model - backend uses its own key
            "endpoint": None,  # Uses internal infrastructure
            "is_protected": True,  # System model - cannot be deleted
            "user_id": uuid.UUID(user_id),
            "owner_id": uuid.UUID(user_id),
        }

        default_model = get_or_create_entity(
            db=db,
            model=models.Model,
            entity_data=default_model_data,
            organization_id=organization_id,
            user_id=user_id,
            commit=False,
        )

        print(f"Created default Rhesis model with ID: {default_model.id}")

        # Flush all changes to ensure they're persisted
        db.flush()

        # Return the default model ID so it can be set in user settings
        return str(default_model.id)

    except Exception:
        # Let the calling code handle transaction rollback
        raise


def _get_model_dependencies(model: Type) -> List[Type]:
    """
    Get a list of models that this model depends on through its relationships.

    Args:
        model: The SQLAlchemy model class

    Returns:
        List of model classes that this model depends on
    """
    dependencies = []
    relationships = inspect(model).relationships

    for rel in relationships:
        # Only consider many-to-one or one-to-one relationships
        # as these indicate dependencies on other models
        if rel.direction.name == "MANYTOONE" or (
            rel.direction.name == "ONETOONE" and not rel.back_populates
        ):
            # Skip self-referential relationships
            if rel.mapper.class_ != model:
                dependencies.append(rel.mapper.class_)

    return dependencies


def _sort_models_by_dependencies(models: List[Type]) -> List[Type]:
    """
    Sort models topologically based on their relationships.
    Models with no dependencies come first, followed by models that depend on them.

    Args:
        models: List of SQLAlchemy model classes

    Returns:
        Sorted list of model classes
    """
    # Create dependency graph
    graph = {model: set(_get_model_dependencies(model)) & set(models) for model in models}

    # Topological sort
    sorted_models = []
    visited = set()
    temp_visited = set()

    def visit(model):
        if model in temp_visited:
            raise ValueError(f"Circular dependency detected involving {model.__name__}")
        if model not in visited:
            temp_visited.add(model)
            for dep in graph[model]:
                visit(dep)
            temp_visited.remove(model)
            visited.add(model)
            sorted_models.append(model)

    # Visit each model
    for model in models:
        if model not in visited:
            visit(model)

    return sorted_models


def _get_nested_entities(db: Session, entity, organization_id: str, visited=None) -> List:
    """
    Recursively get all nested entities for a given entity.

    Args:
        db: Database session
        entity: The entity to get nested entities for
        organization_id: Organization ID to filter by
        visited: Set of already visited entity IDs to prevent cycles

    Returns:
        List of entities to delete in the correct order
    """
    if visited is None:
        visited = set()

    if entity.id in visited:
        return []

    visited.add(entity.id)
    to_delete = [entity]

    # Get all relationships
    relationships = inspect(entity.__class__).relationships

    for rel_name, rel in relationships.items():
        # Skip many-to-many relationships as they're handled separately
        if rel.secondary is not None:
            continue

        # Skip user and organization-related relationships
        if rel.mapper.class_.__name__ in ["User", "Organization"]:
            continue

        # Get the related attribute
        related = getattr(entity, rel_name)

        # Handle collections (one-to-many)
        if rel.uselist:
            if related:
                for item in related:
                    if (
                        hasattr(item, "organization_id")
                        and str(item.organization_id) == organization_id
                        and item.id not in visited
                        and item.__class__.__name__ not in ["User", "Organization"]
                    ):  # Skip User and Organization entities
                        to_delete.extend(_get_nested_entities(db, item, organization_id, visited))
        # Handle scalar (many-to-one, one-to-one)
        elif related is not None:
            if (
                hasattr(related, "organization_id")
                and str(related.organization_id) == organization_id
                and related.id not in visited
                and related.__class__.__name__ not in ["User", "Organization"]
            ):  # Skip User and Organization entities
                to_delete.extend(_get_nested_entities(db, related, organization_id, visited))

    return to_delete


def _get_entity_identifier(model_name: str, item: dict) -> str:
    """Get the identifying field value for an entity."""
    if model_name == "Test":
        return item.get("prompt", "")  # Tests are identified by their prompt
    elif model_name == "Prompt":
        return item.get(
            "content", item.get("prompt", "")
        )  # Prompts can be in content or directly as prompt
    elif model_name == "TypeLookup":
        return item.get("type_value", "")  # TypeLookup uses type_value as identifier
    else:
        return item.get("name", "")  # Default to name for other entities


def _load_initial_data() -> dict:
    """Load and return the initial data from JSON file."""
    script_directory = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_directory, "initial_data.json"), "r") as file:
        return json.load(file)


def _get_model_name(key: str) -> str:
    """Convert JSON key to model name."""
    if key == "status":
        return "Status"
    # Convert snake_case to PascalCase and handle plurals
    model_name = key.lower()
    if model_name.endswith("s"):
        model_name = model_name[:-1]
    return "".join(word.capitalize() for word in model_name.split("_"))


def _build_model_data_map(initial_data: dict) -> dict:
    """Build a map of model names to their entity identifiers."""
    model_data_map = {}

    # Process regular entities
    for key, items in initial_data.items():
        model_name = _get_model_name(key)
        model_data_map[model_name] = {
            _get_entity_identifier(model_name, item)
            for item in items
            if _get_entity_identifier(model_name, item)
        }

    # Process nested entities from test_sets
    if "test_set" in initial_data:
        prompts = set()
        topics = set()
        behaviors = set()
        categories = set()

        for test_set in initial_data["test_set"]:
            if "tests" in test_set:
                for test in test_set["tests"]:
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

    # Remove protected models
    for protected in ["User", "Organization"]:
        model_data_map.pop(protected, None)

    return model_data_map


def _get_matching_records(db: Session, model, identifiers: set, organization_id: str):
    """Get records that match the initial data identifiers."""
    query = (
        QueryBuilder(db, model)
        .with_organization_filter(organization_id)
        .with_custom_filter(lambda q: q.filter(model.organization_id == organization_id))
        .build()
    )

    if model.__name__ == "Test":
        return query.join(models.Prompt).filter(models.Prompt.content.in_(identifiers)).all()
    elif model.__name__ == "TypeLookup":
        return query.filter(model.type_value.in_(identifiers)).all()
    elif hasattr(model, "content"):
        return query.filter(model.content.in_(identifiers)).all()
    else:
        return query.filter(model.name.in_(identifiers)).all()


def _get_entity_identifier_from_instance(entity) -> str:
    """Get identifier from an entity instance."""
    if entity.__class__.__name__ == "Test":
        return entity.prompt.content if entity.prompt else ""
    elif entity.__class__.__name__ == "TypeLookup":
        return entity.type_value
    elif hasattr(entity, "content"):
        return entity.content
    elif hasattr(entity, "name"):
        return entity.name
    return ""


def _delete_entity_associations(db: Session, entity):
    """Delete all many-to-many associations for an entity."""
    for rel in inspect(entity.__class__).relationships:
        if rel.secondary is not None:
            table = rel.secondary
            stmt = table.delete().where(
                getattr(table.c, f"{entity.__class__.__tablename__}_id") == entity.id
            )
            db.execute(stmt)


def rollback_initial_data(db: Session, organization_id: str) -> None:
    """
    Remove all data that was inserted by load_initial_data for a specific organization.
    Only deletes entities that match the data in initial_data.json.
    """
    print(f"\nStarting rollback for organization {organization_id}")
    print(f"Organization ID type: {type(organization_id)}")

    # Load initial data and build model map
    initial_data = _load_initial_data()
    model_data_map = _build_model_data_map(initial_data)

    # Get models to process
    models_to_delete = [
        cls
        for name, cls in models.__dict__.items()
        if isinstance(cls, type)
        and hasattr(cls, "__tablename__")
        and name in model_data_map
        and name not in ["User", "Organization"]
    ]

    try:
        # Sort models by dependencies
        sorted_models = list(reversed(_sort_models_by_dependencies(models_to_delete)))
        entities_to_delete = set()

        # First verify organization state
        print("\nLooking up organization...")
        query = db.query(models.Organization).filter(models.Organization.id == organization_id)
        print(f"SQL Query: {query.statement}")

        org = query.first()
        print(f"Organization lookup result: {org}")
        if org:
            print(
                f"Found organization: ID={org.id}, Name={org.name}, "
                f"Onboarding Complete={org.is_onboarding_complete}"
            )

        if not org:
            print("Organization not found in database!")
            print("Checking all organizations in database:")
            all_orgs = db.query(models.Organization).all()
            for o in all_orgs:
                print(f"Available org: ID={o.id} ({type(o.id)}), Name={o.name}")
            raise ValueError(f"Organization not found with ID: {organization_id}")

        if not org.is_onboarding_complete:
            raise ValueError("Organization not initialized yet")

        # Collect entities to delete
        for model in sorted_models:
            if model.__name__ in ["User", "Organization"]:
                continue

            identifiers = model_data_map.get(model.__name__, set())
            if not identifiers:
                continue

            # Get matching records with eager loading of relationships
            query = (
                QueryBuilder(db, model)
                .with_organization_filter(organization_id)
                .with_joinedloads()
                .with_custom_filter(lambda q: q.filter(model.organization_id == organization_id))
                .build()
            )

            if model.__name__ == "Test":
                records = (
                    query.join(models.Prompt).filter(models.Prompt.content.in_(identifiers)).all()
                )
            elif model.__name__ == "TypeLookup":
                records = query.filter(model.type_value.in_(identifiers)).all()
            elif hasattr(model, "content"):
                records = query.filter(model.content.in_(identifiers)).all()
            else:
                records = query.filter(model.name.in_(identifiers)).all()

            for record in records:
                # Add the record itself if it matches
                if _get_entity_identifier_from_instance(record) in model_data_map[model.__name__]:
                    entities_to_delete.add(record)

                # Add nested entities that match initial data
                for entity in _get_nested_entities(db, record, organization_id):
                    if (
                        entity.__class__.__name__ in model_data_map
                        and _get_entity_identifier_from_instance(entity)
                        in model_data_map[entity.__class__.__name__]
                    ):
                        entities_to_delete.add(entity)

        # Sort entities for deletion
        deletion_order = {
            "Prompt": 0,
            "Test": 1,
            "Topic": 2,
            "Behavior": 2,
            "Category": 2,
            "Metric": 2,
            "TestSet": 3,
            "Project": 4,
        }
        sorted_entities = sorted(
            entities_to_delete, key=lambda e: deletion_order.get(e.__class__.__name__, 999)
        )

        # Delete entities
        deleted_ids = set()
        for entity in sorted_entities:
            if entity.id in deleted_ids:
                continue

            try:
                # Special handling for Status deletion
                # Status entities are referenced by many other entities with NOT NULL constraints
                # We need to delete or update those entities before deleting the Status
                if entity.__class__.__name__ == "Status":
                    # Delete tasks that reference this status
                    # These are typically test-created tasks, not part of initial data
                    tasks_with_status = db.query(models.Task).filter(
                        models.Task.status_id == entity.id,
                        models.Task.organization_id == organization_id
                    ).all()
                    
                    for task in tasks_with_status:
                        try:
                            db.delete(task)
                        except Exception as task_error:
                            print(f"Error deleting task {task.id}: {task_error}")
                    
                    db.flush()
                
                _delete_entity_associations(db, entity)
                db.delete(entity)
                deleted_ids.add(entity.id)
                db.flush()  # Use flush instead of commit to keep transaction atomic
            except Exception as e:
                print(f"Error deleting {entity.__class__.__name__}: {e}")
                continue

        # Update organization status
        org = db.query(models.Organization).filter_by(id=organization_id).first()
        if org:
            org.is_onboarding_complete = False
            db.flush()

        # Transaction commit/rollback is handled by the session context manager

    except Exception as e:
        print(f"\nError during operation: {str(e)}")
        print(f"Error type: {type(e)}")
        raise
