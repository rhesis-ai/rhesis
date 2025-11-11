import base64
import json
import os
import tempfile
from unittest.mock import Mock, patch, mock_open

import pytest
from pydantic import BaseModel
from rhesis.sdk.models.providers.vertex_ai import (
    DEFAULT_MODEL_NAME,
    PROVIDER,
    VertexAILLM,
)


def test_vertex_ai_defaults():
    """Test default constants."""
    assert PROVIDER == "vertex_ai"
    assert DEFAULT_MODEL_NAME == "gemini-2.0-flash"


class TestVertexAILLMInitialization:
    """Test VertexAILLM initialization with different credential methods."""

    def test_init_defaults(self):
        """Test initialization with default model name."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            llm = VertexAILLM()
            assert llm.model_name == f"{PROVIDER}/{DEFAULT_MODEL_NAME}"
            assert llm.model['project'] == "test-project"
            assert llm.model['location'] == "europe-west3"

    def test_init_with_custom_model(self):
        """Test initialization with custom model name."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        custom_model = "gemini-2.0-flash"
        
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "us-central1"
        }, clear=True):
            llm = VertexAILLM(model_name=custom_model)
            assert llm.model_name == f"{PROVIDER}/{custom_model}"

    def test_init_with_parameters(self):
        """Test initialization with direct parameters."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        llm = VertexAILLM(
            model_name="gemini-2.0-flash",
            credentials=encoded_creds,
            location="europe-west3",
            project="custom-project"
        )
        
        assert llm.model_name == f"{PROVIDER}/gemini-2.0-flash"
        assert llm.model['project'] == "custom-project"  # Should use init parameter
        assert llm.model['location'] == "europe-west3"

    def test_init_without_credentials_raises_error(self):
        """Test initialization without credentials raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_APPLICATION_CREDENTIALS not found"):
                VertexAILLM()

    def test_init_without_location_raises_error(self):
        """Test initialization without location raises ValueError."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds
        }, clear=True):
            with pytest.raises(ValueError, match="Vertex AI location not specified"):
                VertexAILLM()


class TestVertexAIConfigLoading:
    """Test credential and configuration loading methods."""

    def test_load_config_base64_credentials(self):
        """Test base64-encoded credentials with location."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key": "test-key",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            llm = VertexAILLM()
            
            assert llm.model['project'] == "test-project-123"
            assert llm.model['location'] == "europe-west3"
            assert llm.model['credentials_path'] is not None
            # Verify temp file was created and exists
            assert os.path.exists(llm.model['credentials_path'])

    def test_load_config_file_credentials(self):
        """Test file path credentials with location."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project-456",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(mock_creds, tf)
            temp_path = tf.name
        
        try:
            with patch.dict(os.environ, {
                "GOOGLE_APPLICATION_CREDENTIALS": temp_path,
                "VERTEX_AI_LOCATION": "us-central1"
            }, clear=True):
                llm = VertexAILLM()
                
                assert llm.model['project'] == "test-project-456"
                assert llm.model['location'] == "us-central1"
                # When using file path, credentials_path should match the provided path
                assert llm.model['credentials_path'] == temp_path
        finally:
            os.unlink(temp_path)

    def test_load_config_file_with_location(self):
        """Test file path with explicit location."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project-789",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(mock_creds, tf)
            temp_path = tf.name
        
        try:
            with patch.dict(os.environ, {
                "GOOGLE_APPLICATION_CREDENTIALS": temp_path,
                "VERTEX_AI_LOCATION": "asia-northeast1"
            }, clear=True):
                llm = VertexAILLM()
                
                assert llm.model['project'] == "test-project-789"
                assert llm.model['location'] == "asia-northeast1"
                assert llm.model['credentials_path'] == temp_path
                # Verify file path credentials don't create a temp file
                assert not llm.model['credentials_path'].startswith('/var/folders') or \
                       llm.model['credentials_path'] == temp_path
        finally:
            os.unlink(temp_path)

    def test_load_config_project_override(self):
        """Test that VERTEX_AI_PROJECT overrides credentials project."""
        mock_creds = {
            "type": "service_account",
            "project_id": "original-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3",
            "VERTEX_AI_PROJECT": "override-project"
        }, clear=True):
            llm = VertexAILLM()
            assert llm.model['project'] == "override-project"

    def test_load_config_invalid_base64(self):
        """Test that invalid base64 credentials raise error."""
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": "not-valid-base64!@#$",
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            with pytest.raises(ValueError, match="is neither valid base64 nor an existing file path"):
                VertexAILLM()

    def test_load_config_file_not_found(self):
        """Test that non-existent credentials file raises error."""
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": "/non/existent/path.json",
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            with pytest.raises(ValueError, match="is neither valid base64 nor an existing file path"):
                VertexAILLM()

    def test_load_config_missing_project(self):
        """Test that missing project raises error."""
        mock_creds = {
            "type": "service_account",
            "client_email": "test@test.iam.gserviceaccount.com",
            # No project_id
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            with pytest.raises(ValueError, match="Could not determine VERTEX_AI_PROJECT"):
                VertexAILLM()


class TestVertexAIGenerate:
    """Test generate method functionality."""

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema(self, mock_completion):
        """Test generate method without schema returns string response."""
        # Setup mock credentials
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello from Vertex AI"
        mock_completion.return_value = mock_response

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            llm = VertexAILLM()
            prompt = "Hello, how are you?"
            
            result = llm.generate(prompt)
            
            assert result == "Hello from Vertex AI"
            
            # Check that completion was called with vertex_ai parameters
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs['vertex_ai_project'] == "test-project"
            assert call_kwargs['vertex_ai_location'] == "europe-west3"

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema(self, mock_completion):
        """Test generate method with schema returns validated dict response."""
        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Setup mock credentials
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        # Mock the completion response with JSON string
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "John", "age": 30, "city": "New York"}'
        mock_completion.return_value = mock_response

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "us-central1"
        }, clear=True):
            llm = VertexAILLM()
            prompt = "Generate a person's information"
            
            result = llm.generate(prompt, schema=TestSchema)
            
            assert isinstance(result, dict)
            assert result["name"] == "John"
            assert result["age"] == 30
            assert result["city"] == "New York"

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_system_prompt(self, mock_completion):
        """Test generate method with system prompt."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            llm = VertexAILLM()
            prompt = "Test prompt"
            system_prompt = "You are a helpful assistant"
            
            llm.generate(prompt, system_prompt=system_prompt)
            
            # Check messages include system prompt
            messages = mock_completion.call_args[1]['messages']
            assert len(messages) == 2
            assert messages[0]['role'] == 'system'
            assert messages[0]['content'] == system_prompt

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_additional_kwargs(self, mock_completion):
        """Test generate method passes additional kwargs to completion."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west1"
        }, clear=True):
            llm = VertexAILLM()
            prompt = "Test prompt"
            
            llm.generate(prompt, temperature=0.7, max_tokens=100)
            
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs['temperature'] == 0.7
            assert call_kwargs['max_tokens'] == 100
            assert call_kwargs['vertex_ai_project'] == "test-project"
            assert call_kwargs['vertex_ai_location'] == "europe-west1"

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_restores_credentials_env_var(self, mock_completion):
        """Test that generate properly restores the original GOOGLE_APPLICATION_CREDENTIALS."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        # Set an original value
        original_value = "/path/to/original/credentials.json"
        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "asia-northeast1"
        }, clear=True):
            # Set a different value before calling generate
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = original_value
            
            llm = VertexAILLM(credentials=encoded_creds, location="asia-northeast1")
            prompt = "Test prompt"
            
            llm.generate(prompt)
            
            # Verify it was restored
            assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == original_value


class TestVertexAIUtilityMethods:
    """Test utility methods."""

    def test_get_config_info_base64_credentials(self):
        """Test get_config_info returns correct information for base64 credentials."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            llm = VertexAILLM(model_name="gemini-2.0-flash")
            config = llm.get_config_info()
            
            assert config['provider'] == "vertex_ai"
            assert config['model'] == "vertex_ai/gemini-2.0-flash"
            assert config['project'] == "test-project"
            assert config['location'] == "europe-west3"
            assert config['credentials_source'] == "base64"
            assert config['credentials_path'] is not None

    def test_get_config_info_file_credentials(self):
        """Test get_config_info returns correct information for file credentials."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(mock_creds, tf)
            temp_path = tf.name
        
        try:
            with patch.dict(os.environ, {
                "GOOGLE_APPLICATION_CREDENTIALS": temp_path,
                "VERTEX_AI_LOCATION": "us-central1"
            }, clear=True):
                llm = VertexAILLM()
                config = llm.get_config_info()
                
                assert config['credentials_source'] == "file"
                assert config['credentials_path'] == temp_path
        finally:
            os.unlink(temp_path)


class TestVertexAIRegionalLocations:
    """Test different regional locations."""

    @pytest.mark.parametrize("location", [
        "europe-west1",
        "europe-west3",
        "europe-west4",
        "us-central1",
        "us-east4",
        "asia-northeast1",
        "asia-southeast1",
    ])
    def test_regional_locations(self, location):
        """Test that various regional locations are set correctly."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": location
        }, clear=True):
            llm = VertexAILLM()
            assert llm.model['location'] == location


class TestVertexAICleanup:
    """Test cleanup of temporary files."""

    def test_temp_file_cleanup_on_delete(self):
        """Test that temporary credentials file is tracked and exists."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(os.environ, {
            "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
            "VERTEX_AI_LOCATION": "europe-west3"
        }, clear=True):
            llm = VertexAILLM()
            credentials_path = llm.model.get('credentials_path')
            
            # Credentials path should be set
            assert credentials_path is not None
            # Temp file should exist
            assert os.path.exists(credentials_path)
            
            # Verify it's a temp file (deterministic path based on credentials hash)
            assert 'vertex_ai_creds_' in credentials_path
            
            # Delete the instance - temp file will be cleaned up at process exit via atexit
            del llm
            
            # Temp file persists until process exit (cleaned up via atexit)
            # This is intentional to allow multiple instances to share the same file
            assert os.path.exists(credentials_path)

