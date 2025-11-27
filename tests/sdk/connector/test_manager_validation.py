"""Tests for ConnectorManager validation (environment and project_id)."""

import pytest

from rhesis.sdk.connector.manager import ConnectorManager


class TestEnvironmentValidation:
    """Test environment validation in ConnectorManager."""

    def test_environment_validation_lowercase_production(self):
        """Valid lowercase 'production' environment should work."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="production",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "production"

    def test_environment_validation_lowercase_staging(self):
        """Valid lowercase 'staging' environment should work."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="staging",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "staging"

    def test_environment_validation_lowercase_development(self):
        """Valid lowercase 'development' environment should work."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="development",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "development"

    def test_environment_validation_lowercase_local(self):
        """Valid lowercase 'local' environment should work."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="local",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "local"

    def test_environment_validation_mixed_case_production(self):
        """Mixed case 'Production' should normalize to lowercase."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="Production",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "production"

    def test_environment_validation_mixed_case_staging(self):
        """Mixed case 'Staging' should normalize to lowercase."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="Staging",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "staging"

    def test_environment_validation_uppercase_development(self):
        """Uppercase 'DEVELOPMENT' should normalize to lowercase."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="DEVELOPMENT",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "development"

    def test_environment_validation_mixed_case_local(self):
        """Mixed case 'LoCAl' should normalize to lowercase."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="LoCAl",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "local"

    def test_environment_validation_invalid_string(self):
        """Invalid environment string should raise ValueError with clear message."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="invalid-env",
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        assert "Invalid environment" in error_message
        assert "invalid-env" in error_message
        assert "production" in error_message
        assert "staging" in error_message
        assert "development" in error_message
        assert "local" in error_message

    def test_environment_validation_typo(self):
        """Typo in environment (e.g., 'devlopment') should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="devlopment",  # Missing 'e'
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        assert "Invalid environment" in error_message
        assert "devlopment" in error_message

    def test_environment_validation_empty_string(self):
        """Empty environment string should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="",
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        assert "Invalid environment" in error_message

    def test_environment_validation_special_characters(self):
        """Environment with special characters should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="dev@prod!",
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        assert "Invalid environment" in error_message

    def test_environment_validation_numeric(self):
        """Numeric environment string should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="12345",
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        assert "Invalid environment" in error_message

    def test_environment_default_value(self):
        """Default environment should be 'development'."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            base_url="http://localhost:8080",
        )
        assert manager.environment == "development"


class TestEnvironmentErrorMessages:
    """Test error messages for environment validation."""

    def test_error_message_includes_valid_values(self):
        """Error message should list all valid environments."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="wrong",
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        # Check that all valid environments are mentioned
        valid_envs = ["production", "staging", "development", "local"]
        for env in valid_envs:
            assert env in error_message, f"Valid environment '{env}' not in error message"

    def test_error_message_includes_invalid_value(self):
        """Error message should include the invalid value provided."""
        invalid_env = "my-custom-env"
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment=invalid_env,
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        assert invalid_env in error_message

    def test_error_message_format(self):
        """Error message should be clear and actionable."""
        with pytest.raises(ValueError) as exc_info:
            ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment="test-env",
                base_url="http://localhost:8080",
            )

        error_message = str(exc_info.value)
        # Should start with clear indicator
        assert error_message.startswith("Invalid environment")
        # Should provide guidance
        assert "Valid environments" in error_message


class TestEnvironmentNormalization:
    """Test environment normalization to lowercase."""

    @pytest.mark.parametrize(
        "input_env,expected",
        [
            ("production", "production"),
            ("PRODUCTION", "production"),
            ("Production", "production"),
            ("PrOdUcTiOn", "production"),
            ("staging", "staging"),
            ("STAGING", "staging"),
            ("Staging", "staging"),
            ("StAgInG", "staging"),
            ("development", "development"),
            ("DEVELOPMENT", "development"),
            ("Development", "development"),
            ("local", "local"),
            ("LOCAL", "local"),
            ("Local", "local"),
        ],
    )
    def test_environment_normalization(self, input_env, expected):
        """Test that various casings normalize to lowercase."""
        manager = ConnectorManager(
            api_key="test-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment=input_env,
            base_url="http://localhost:8080",
        )
        assert manager.environment == expected


class TestAllValidEnvironments:
    """Test that all 4 valid environments work correctly."""

    def test_all_valid_environments_accepted(self):
        """All 4 valid environments should be accepted."""
        valid_environments = ["production", "staging", "development", "local"]

        for env in valid_environments:
            manager = ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment=env,
                base_url="http://localhost:8080",
            )
            assert manager.environment == env, f"Environment '{env}' was not properly set"

    def test_all_environments_with_mixed_case(self):
        """All 4 valid environments should work with mixed case."""
        environments_mixed_case = [
            ("Production", "production"),
            ("STAGING", "staging"),
            ("Development", "development"),
            ("LOCAL", "local"),
        ]

        for input_env, expected_env in environments_mixed_case:
            manager = ConnectorManager(
                api_key="test-key",
                project_id="123e4567-e89b-12d3-a456-426614174000",
                environment=input_env,
                base_url="http://localhost:8080",
            )
            assert manager.environment == expected_env, (
                f"Environment '{input_env}' did not normalize to '{expected_env}'"
            )


class TestManagerInitialization:
    """Test manager initialization with various valid configurations."""

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters specified."""
        manager = ConnectorManager(
            api_key="my-api-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="staging",
            base_url="https://api.example.com",
        )

        assert manager.api_key == "my-api-key"
        assert manager.project_id == "123e4567-e89b-12d3-a456-426614174000"
        assert manager.environment == "staging"
        assert manager.base_url == "https://api.example.com"

    def test_initialization_with_defaults(self):
        """Test initialization with default values."""
        manager = ConnectorManager(
            api_key="my-api-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
        )

        assert manager.environment == "development"
        assert manager.base_url == "ws://localhost:8080"

    def test_initialization_environment_normalized(self):
        """Test that environment is normalized during initialization."""
        manager = ConnectorManager(
            api_key="my-api-key",
            project_id="123e4567-e89b-12d3-a456-426614174000",
            environment="PRODUCTION",
        )

        # Environment should be normalized to lowercase
        assert manager.environment == "production"

    def test_initialization_preserves_other_fields(self):
        """Test that environment validation doesn't affect other fields."""
        api_key = "my-special-key-123"
        project_id = "123e4567-e89b-12d3-a456-426614174000"
        base_url = "https://custom.api.com"

        manager = ConnectorManager(
            api_key=api_key,
            project_id=project_id,
            environment="staging",
            base_url=base_url,
        )

        # All other fields should be preserved exactly
        assert manager.api_key == api_key
        assert manager.project_id == project_id
        assert manager.base_url == base_url
