"""Tests for Test entity with test_configuration convenience fields."""

import os

from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.entities.test import Test, TestConfiguration

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


def test_test_with_test_configuration_object():
    """Test that Test accepts TestConfiguration object directly."""
    config = TestConfiguration(
        goal="Test the system",
        instructions="Follow these steps",
        restrictions="Do not do this",
        scenario="In this context",
    )

    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        prompt=Prompt(content="Test prompt"),
        test_configuration=config,
    )

    assert test.test_configuration is not None
    assert test.test_configuration.goal == "Test the system"
    assert test.test_configuration.instructions == "Follow these steps"
    assert test.test_configuration.restrictions == "Do not do this"
    assert test.test_configuration.scenario == "In this context"


def test_test_with_separate_fields():
    """Test that Test builds test_configuration from separate fields (multi-turn test)."""
    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        goal="Test the system",
        instructions="Follow these steps",
        restrictions="Do not do this",
        scenario="In this context",
    )

    assert test.test_configuration is not None
    assert test.test_configuration.goal == "Test the system"
    assert test.test_configuration.instructions == "Follow these steps"
    assert test.test_configuration.restrictions == "Do not do this"
    assert test.test_configuration.scenario == "In this context"


def test_test_with_only_goal():
    """Test that Test builds test_configuration with only goal (others default to empty)."""
    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        goal="Test the system",
    )

    assert test.test_configuration is not None
    assert test.test_configuration.goal == "Test the system"
    assert test.test_configuration.instructions == ""
    assert test.test_configuration.restrictions == ""
    assert test.test_configuration.scenario == ""


def test_test_without_goal_or_config():
    """Test that Test without goal or test_configuration has None config."""
    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        prompt=Prompt(content="Test prompt"),
    )

    assert test.test_configuration is None


def test_test_configuration_takes_precedence():
    """Test that explicit test_configuration takes precedence over separate fields."""
    config = TestConfiguration(
        goal="Config goal",
        instructions="Config instructions",
    )

    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        test_configuration=config,
        goal="Separate goal",  # Should be ignored
        instructions="Separate instructions",  # Should be ignored
    )

    assert test.test_configuration is not None
    assert test.test_configuration.goal == "Config goal"
    assert test.test_configuration.instructions == "Config instructions"


def test_test_with_partial_fields():
    """Test that Test handles partial separate fields correctly (multi-turn test)."""
    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        goal="Test the system",
        restrictions="Do not do this",
        # instructions and scenario not provided
    )

    assert test.test_configuration is not None
    assert test.test_configuration.goal == "Test the system"
    assert test.test_configuration.instructions == ""
    assert test.test_configuration.restrictions == "Do not do this"
    assert test.test_configuration.scenario == ""


def test_single_turn_with_prompt():
    """Test that single-turn tests can have both prompt and no test_configuration."""
    test = Test(
        category="Safety",
        topic="Test",
        behavior="Refusal",
        prompt=Prompt(content="Test prompt"),
    )

    assert test.prompt is not None
    assert test.prompt.content == "Test prompt"
    assert test.test_configuration is None
