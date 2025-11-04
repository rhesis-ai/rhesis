"""Tests for PenelopeConfig."""

import logging
import pytest
from rhesis.penelope.config import PenelopeConfig


def test_config_default_log_level():
    """Test that default log level is INFO."""
    PenelopeConfig.reset()
    level = PenelopeConfig.get_log_level()
    assert level == "INFO"


def test_config_set_log_level():
    """Test programmatic log level setting."""
    PenelopeConfig.set_log_level("DEBUG")
    assert PenelopeConfig.get_log_level() == "DEBUG"

    PenelopeConfig.set_log_level("warning")
    assert PenelopeConfig.get_log_level() == "WARNING"

    # Cleanup
    PenelopeConfig.reset()


def test_config_env_variable(monkeypatch):
    """Test that environment variable overrides default."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_LOG_LEVEL", "ERROR")

    level = PenelopeConfig.get_log_level()
    assert level == "ERROR"

    # Cleanup
    PenelopeConfig.reset()


def test_config_programmatic_overrides_env(monkeypatch):
    """Test that programmatic setting overrides environment variable."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_LOG_LEVEL", "ERROR")

    # Set programmatically
    PenelopeConfig.set_log_level("DEBUG")

    # Should use programmatic value
    assert PenelopeConfig.get_log_level() == "DEBUG"

    # Cleanup
    PenelopeConfig.reset()


def test_config_initialize():
    """Test configuration initialization."""
    PenelopeConfig.reset()
    assert not PenelopeConfig._initialized

    PenelopeConfig.initialize()
    assert PenelopeConfig._initialized

    # Second call should be no-op
    PenelopeConfig.initialize()
    assert PenelopeConfig._initialized

    # Cleanup
    PenelopeConfig.reset()


def test_config_apply_logging():
    """Test that logging configuration is applied."""
    PenelopeConfig.reset()

    # Set to DEBUG
    PenelopeConfig.set_log_level("DEBUG")

    # Check that Penelope logger has correct level
    penelope_logger = logging.getLogger("rhesis.penelope")
    assert penelope_logger.level == logging.DEBUG

    # Set to WARNING
    PenelopeConfig.set_log_level("WARNING")
    assert penelope_logger.level == logging.WARNING

    # Cleanup
    PenelopeConfig.reset()


def test_config_suppress_external_loggers():
    """Test that external loggers are suppressed in non-DEBUG mode."""
    PenelopeConfig.reset()

    # Set to INFO (should suppress external loggers)
    PenelopeConfig.set_log_level("INFO")

    # Check that external loggers are at WARNING level
    litellm_logger = logging.getLogger("LiteLLM")
    httpx_logger = logging.getLogger("httpx")

    assert litellm_logger.level == logging.WARNING
    assert httpx_logger.level == logging.WARNING

    # Cleanup
    PenelopeConfig.reset()


def test_config_enable_external_loggers():
    """Test that external loggers are enabled in DEBUG mode."""
    PenelopeConfig.reset()

    # Set to DEBUG (should enable external loggers)
    PenelopeConfig.set_log_level("DEBUG")

    # Check that external loggers are at DEBUG level
    litellm_logger = logging.getLogger("LiteLLM")
    httpx_logger = logging.getLogger("httpx")

    assert litellm_logger.level == logging.DEBUG
    assert httpx_logger.level == logging.DEBUG

    # Cleanup
    PenelopeConfig.reset()


def test_config_reset():
    """Test configuration reset."""
    PenelopeConfig.set_log_level("DEBUG")
    PenelopeConfig.set_default_model("anthropic", "claude-4")
    PenelopeConfig.set_default_max_iterations(30)
    PenelopeConfig.initialize()

    assert PenelopeConfig._initialized
    assert PenelopeConfig._log_level == "DEBUG"
    assert PenelopeConfig._default_model == "anthropic"
    assert PenelopeConfig._default_max_iterations == 30

    PenelopeConfig.reset()

    assert not PenelopeConfig._initialized
    assert PenelopeConfig._log_level is None
    assert PenelopeConfig._default_model is None
    assert PenelopeConfig._default_model_name is None
    assert PenelopeConfig._default_max_iterations is None


def test_config_default_model():
    """Test default model configuration."""
    PenelopeConfig.reset()
    
    # Should default to vertex_ai
    model = PenelopeConfig.get_default_model()
    assert model == "vertex_ai"
    
    # Should default to gemini-2.0-flash
    model_name = PenelopeConfig.get_default_model_name()
    assert model_name == "gemini-2.0-flash"
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_set_default_model():
    """Test programmatic default model setting."""
    PenelopeConfig.set_default_model("anthropic", "claude-4")
    
    assert PenelopeConfig.get_default_model() == "anthropic"
    assert PenelopeConfig.get_default_model_name() == "claude-4"
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_default_model_env_variable(monkeypatch):
    """Test that environment variable overrides default model."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_DEFAULT_MODEL", "openai")
    monkeypatch.setenv("PENELOPE_DEFAULT_MODEL_NAME", "gpt-4")
    
    model = PenelopeConfig.get_default_model()
    model_name = PenelopeConfig.get_default_model_name()
    
    assert model == "openai"
    assert model_name == "gpt-4"
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_programmatic_overrides_env_model(monkeypatch):
    """Test that programmatic setting overrides environment variable for model."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_DEFAULT_MODEL", "openai")
    monkeypatch.setenv("PENELOPE_DEFAULT_MODEL_NAME", "gpt-4")
    
    # Set programmatically
    PenelopeConfig.set_default_model("anthropic", "claude-4")
    
    # Should use programmatic value
    assert PenelopeConfig.get_default_model() == "anthropic"
    assert PenelopeConfig.get_default_model_name() == "claude-4"
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_default_max_iterations():
    """Test default max iterations configuration."""
    PenelopeConfig.reset()
    
    # Should default to 10
    max_iterations = PenelopeConfig.get_default_max_iterations()
    assert max_iterations == 10
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_set_default_max_iterations():
    """Test programmatic max iterations setting."""
    PenelopeConfig.set_default_max_iterations(30)
    
    assert PenelopeConfig.get_default_max_iterations() == 30
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_set_invalid_max_iterations():
    """Test that setting invalid max iterations raises error."""
    import pytest
    
    with pytest.raises(ValueError, match="max_iterations must be positive"):
        PenelopeConfig.set_default_max_iterations(0)
    
    with pytest.raises(ValueError, match="max_iterations must be positive"):
        PenelopeConfig.set_default_max_iterations(-5)
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_default_max_iterations_env_variable(monkeypatch):
    """Test that environment variable overrides default max iterations."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_DEFAULT_MAX_ITERATIONS", "50")
    
    max_iterations = PenelopeConfig.get_default_max_iterations()
    
    assert max_iterations == 50
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_default_max_iterations_invalid_env_variable(monkeypatch):
    """Test that invalid environment variable falls back to default."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_DEFAULT_MAX_ITERATIONS", "not_a_number")
    
    max_iterations = PenelopeConfig.get_default_max_iterations()
    
    # Should fall back to default
    assert max_iterations == 10
    
    # Cleanup
    PenelopeConfig.reset()


def test_config_programmatic_overrides_env_max_iterations(monkeypatch):
    """Test that programmatic setting overrides environment variable for max iterations."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_DEFAULT_MAX_ITERATIONS", "50")
    
    # Set programmatically
    PenelopeConfig.set_default_max_iterations(30)
    
    # Should use programmatic value
    assert PenelopeConfig.get_default_max_iterations() == 30
    
    # Cleanup
    PenelopeConfig.reset()

