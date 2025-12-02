import uuid
from typing import Type, Dict, Any, Optional, get_type_hints
from faker import Faker
from pydantic import BaseModel, Field
from inspect import signature

fake = Faker()


def generate_mock_data(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Generate mock data for a given Pydantic model.

    Args:
        model (Type[BaseModel]): The Pydantic model class.

    Returns:
        Dict[str, Any]: A dictionary of mock data.
    """
    mock_data = {}

    # Get type hints for the model
    type_hints = get_type_hints(model)

    for field_name, field_info in type_hints.items():
        default_factory = None
        if field_name in model.model_fields:
            field = model.model_fields[field_name]
            if hasattr(field, "default_factory"):
                default_factory = field.default_factory

        # Handle optional fields
        if getattr(field_info, "__origin__", None) is Optional:
            field_type = field_info.__args__[0]
        else:
            field_type = field_info

        if default_factory:
            mock_data[field_name] = default_factory()
        elif field_type == str:
            mock_data[field_name] = fake.word()
        elif field_type == int:
            mock_data[field_name] = fake.random_int()
        elif field_type == float:
            mock_data[field_name] = fake.random_number()
        elif field_type == bool:
            mock_data[field_name] = fake.boolean()
        elif field_type == Optional[str]:
            mock_data[field_name] = fake.word() if fake.boolean() else None
        elif field_type == Optional[int]:
            mock_data[field_name] = fake.random_int() if fake.boolean() else None
        elif field_type == Optional[float]:
            mock_data[field_name] = fake.random_number() if fake.boolean() else None
        elif field_type == Optional[bool]:
            mock_data[field_name] = fake.boolean() if fake.boolean() else None
        elif field_type == Optional[uuid.UUID]:
            pass  # Do not generate UUIDs for these fields, because generating UUIDs is taken care of by the database
        else:
            mock_data[field_name] = str(fake.pystr())  # Default to string for unknown types

    return mock_data
