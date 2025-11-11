"""Tests for system prompt assembly with restrictions."""

import pytest
from rhesis.penelope.prompts.system.system_assembly import get_system_prompt
from rhesis.penelope.prompts.system.system_assembly_jinja import get_system_prompt_jinja


def test_get_system_prompt_basic():
    """Test basic system prompt generation."""
    prompt = get_system_prompt(
        instructions="Test the chatbot",
        goal="Verify responses are accurate",
    )
    
    assert "Test the chatbot" in prompt
    assert "Verify responses are accurate" in prompt
    assert "Test Instructions:" in prompt
    assert "Test Goal:" in prompt


def test_get_system_prompt_with_scenario():
    """Test system prompt with scenario."""
    prompt = get_system_prompt(
        instructions="Test the chatbot",
        goal="Verify responses",
        scenario="You are a frustrated customer",
    )
    
    assert "You are a frustrated customer" in prompt
    assert "Test Scenario:" in prompt


def test_get_system_prompt_with_restrictions():
    """Test system prompt includes restrictions."""
    prompt = get_system_prompt(
        instructions="Test the chatbot",
        goal="Verify security boundaries",
        restrictions="Do not use profanity\nAvoid offensive content",
    )
    
    assert "Do not use profanity" in prompt
    assert "Avoid offensive content" in prompt
    assert "Test Restrictions:" in prompt


def test_get_system_prompt_with_all_fields():
    """Test system prompt with all fields including restrictions."""
    prompt = get_system_prompt(
        instructions="Test security vulnerabilities",
        goal="Find potential security issues",
        scenario="Adversarial security researcher",
        restrictions="Only test authorized systems\nDo not cause actual damage",
        context="Testing environment: staging",
        available_tools="send_message, analyze",
    )
    
    assert "Test security vulnerabilities" in prompt
    assert "Find potential security issues" in prompt
    assert "Adversarial security researcher" in prompt
    assert "Only test authorized systems" in prompt
    assert "Do not cause actual damage" in prompt
    assert "Testing environment: staging" in prompt
    assert "send_message, analyze" in prompt


def test_get_system_prompt_restrictions_positioning():
    """Test that restrictions appear after goal and before context."""
    prompt = get_system_prompt(
        instructions="Test instructions",
        goal="Test goal",
        restrictions="Test restrictions",
        context="Test context",
    )
    
    goal_pos = prompt.find("Test Goal:")
    restrictions_pos = prompt.find("Test Restrictions:")
    context_pos = prompt.find("Context & Resources:")
    
    assert goal_pos < restrictions_pos < context_pos


def test_get_system_prompt_empty_restrictions():
    """Test system prompt with empty restrictions string."""
    prompt = get_system_prompt(
        instructions="Test instructions",
        goal="Test goal",
        restrictions="",
    )
    
    # Should not include restrictions section when empty
    assert "Test Restrictions:" not in prompt


def test_get_system_prompt_jinja_with_restrictions():
    """Test Jinja2-based system prompt with restrictions."""
    prompt = get_system_prompt_jinja(
        instructions="Test the chatbot",
        goal="Verify security boundaries",
        restrictions="Do not use profanity\nAvoid offensive content",
    )
    
    assert "Do not use profanity" in prompt
    assert "Avoid offensive content" in prompt
    assert "Test Restrictions:" in prompt


def test_get_system_prompt_jinja_no_restrictions():
    """Test Jinja2 prompt without restrictions (None handling)."""
    prompt = get_system_prompt_jinja(
        instructions="Test instructions",
        goal="Test goal",
        restrictions="",  # Empty string should be converted to None
    )
    
    # Should not include restrictions section when empty
    assert "Test Restrictions:" not in prompt


def test_get_system_prompt_jinja_with_all_fields():
    """Test Jinja2 system prompt with all fields."""
    prompt = get_system_prompt_jinja(
        instructions="Test security",
        goal="Find issues",
        scenario="Security researcher",
        restrictions="Stay ethical\nReport responsibly",
        context="Staging environment",
        available_tools="tools available",
    )
    
    assert "Test security" in prompt
    assert "Find issues" in prompt
    assert "Security researcher" in prompt
    assert "Stay ethical" in prompt
    assert "Report responsibly" in prompt
    assert "Staging environment" in prompt


def test_restrictions_multi_line_formatting():
    """Test that multi-line restrictions are properly formatted."""
    restrictions = """
    - Do not use profanity
    - Avoid offensive content
    - Stay within scope
    - Report findings responsibly
    """
    
    prompt = get_system_prompt(
        instructions="Test instructions",
        goal="Test goal",
        restrictions=restrictions,
    )
    
    assert "Do not use profanity" in prompt
    assert "Avoid offensive content" in prompt
    assert "Stay within scope" in prompt
    assert "Report findings responsibly" in prompt


def test_restrictions_with_special_characters():
    """Test restrictions with special characters."""
    restrictions = "Do not test: payment, admin, or user deletion features"
    
    prompt = get_system_prompt(
        instructions="Test instructions",
        goal="Test goal",
        restrictions=restrictions,
    )
    
    assert "Do not test: payment, admin, or user deletion features" in prompt


def test_system_prompt_consistency_python_vs_jinja():
    """Test that Python and Jinja2 versions produce consistent output."""
    python_prompt = get_system_prompt(
        instructions="Test instructions",
        goal="Test goal",
        scenario="Test scenario",
        restrictions="Test restrictions",
        context="Test context",
    )
    
    jinja_prompt = get_system_prompt_jinja(
        instructions="Test instructions",
        goal="Test goal",
        scenario="Test scenario",
        restrictions="Test restrictions",
        context="Test context",
    )
    
    # Both should contain the same key sections
    for section in ["Test Instructions:", "Test Goal:", "Test Restrictions:", "Context & Resources:"]:
        assert section in python_prompt
        assert section in jinja_prompt

