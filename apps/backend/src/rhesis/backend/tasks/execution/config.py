from typing import Dict
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration


class TestConfigurationError(Exception):
    """Exception raised for errors in test configuration."""

    pass


def get_test_configuration(session: Session, test_configuration_id: str) -> TestConfiguration:
    """Retrieve and validate test configuration."""
    # Use the crud utility directly
    test_config = crud.get_test_configuration(session, test_configuration_id=UUID(test_configuration_id))

    if not test_config:
        raise ValueError(f"Test configuration {test_configuration_id} not found")

    if not test_config.test_set_id:
        raise ValueError(f"Test configuration {test_configuration_id} has no test set assigned")

    return test_config 