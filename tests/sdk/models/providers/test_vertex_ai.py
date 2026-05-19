import asyncio
import base64
import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.vertex_ai import (
    DEFAULT_MODEL_NAME,
    VertexAILLM,
)


def test_vertex_ai_defaults():
    """Test default constants."""
    assert VertexAILLM.PROVIDER == "vertex_ai"
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

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()
            assert llm.model_name == f"{VertexAILLM.PROVIDER}/{DEFAULT_MODEL_NAME}"
            assert llm.model["project"] == "test-project"
            assert llm.model["location"] == "europe-west3"

    def test_init_with_custom_model(self):
        """Test initialization with custom model name."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()
        custom_model = "gemini-2.0-flash"

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "us-central1"},
            clear=True,
        ):
            llm = VertexAILLM(model_name=custom_model)
            assert llm.model_name == f"{VertexAILLM.PROVIDER}/{custom_model}"

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
            project="custom-project",
        )

        assert llm.model_name == f"{VertexAILLM.PROVIDER}/gemini-2.0-flash"
        assert llm.model["project"] == "custom-project"  # Should use init parameter
        assert llm.model["location"] == "europe-west3"

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

        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds}, clear=True):
            with pytest.raises(ValueError, match="Vertex AI location not specified"):
                VertexAILLM()


class TestVertexAIConfigLoading:
    """Test credential and configuration loading methods."""

    def test_load_config_base64_credentials(self):
        """Test base64-encoded credentials are kept in memory as JSON."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key": "test-key",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()

            assert llm.model["project"] == "test-project-123"
            assert llm.model["location"] == "europe-west3"
            assert llm.model["credentials_source"] == "base64"
            creds_roundtrip = json.loads(llm.model["vertex_credentials"])
            assert creds_roundtrip["project_id"] == "test-project-123"

    def test_load_config_file_credentials(self):
        """Test file path credentials with location."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project-456",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(mock_creds, tf)
            temp_path = tf.name

        try:
            with patch.dict(
                os.environ,
                {"GOOGLE_APPLICATION_CREDENTIALS": temp_path, "VERTEX_AI_LOCATION": "us-central1"},
                clear=True,
            ):
                llm = VertexAILLM()

                assert llm.model["project"] == "test-project-456"
                assert llm.model["location"] == "us-central1"
                assert llm.model["credentials_source"] == "file"
                assert llm.model["vertex_credentials"] == temp_path
        finally:
            os.unlink(temp_path)

    def test_load_config_file_with_location(self):
        """Test file path with explicit location."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project-789",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(mock_creds, tf)
            temp_path = tf.name

        try:
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_APPLICATION_CREDENTIALS": temp_path,
                    "VERTEX_AI_LOCATION": "asia-northeast1",
                },
                clear=True,
            ):
                llm = VertexAILLM()

                assert llm.model["project"] == "test-project-789"
                assert llm.model["location"] == "asia-northeast1"
                assert llm.model["vertex_credentials"] == temp_path
                assert llm.model["credentials_source"] == "file"
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

        with patch.dict(
            os.environ,
            {
                "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
                "VERTEX_AI_LOCATION": "europe-west3",
                "VERTEX_AI_PROJECT": "override-project",
            },
            clear=True,
        ):
            llm = VertexAILLM()
            assert llm.model["project"] == "override-project"

    def test_load_config_invalid_base64(self):
        """Test that invalid base64 credentials raise error without leaking value."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_APPLICATION_CREDENTIALS": "not-valid-base64!@#$",
                "VERTEX_AI_LOCATION": "europe-west3",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="could not be loaded") as exc_info:
                VertexAILLM()
            # Ensure the raw credential value is NOT in the error message
            assert "not-valid-base64!@#$" not in str(exc_info.value)

    def test_load_config_file_not_found(self):
        """Test that non-existent credentials file raises error."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_APPLICATION_CREDENTIALS": "/non/existent/path.json",
                "VERTEX_AI_LOCATION": "europe-west3",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="could not be loaded"):
                VertexAILLM()

    def test_load_config_missing_project(self):
        """Test that missing project raises error."""
        mock_creds = {
            "type": "service_account",
            "client_email": "test@test.iam.gserviceaccount.com",
            # No project_id
        }

        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            with pytest.raises(ValueError, match="Could not determine VERTEX_AI_PROJECT"):
                VertexAILLM()


class TestVertexAIGenerate:
    """Test generate method functionality."""

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
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

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()
            prompt = "Hello, how are you?"

            result = llm.generate(prompt)

            assert result == "Hello from Vertex AI"

            # Check that completion was called with vertex_ai parameters
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["vertex_ai_project"] == "test-project"
            assert call_kwargs["vertex_ai_location"] == "europe-west3"

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
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

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "us-central1"},
            clear=True,
        ):
            llm = VertexAILLM()
            prompt = "Generate a person's information"

            result = llm.generate(prompt, schema=TestSchema)

            assert isinstance(result, dict)
            assert result["name"] == "John"
            assert result["age"] == 30
            assert result["city"] == "New York"

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
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

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()
            prompt = "Test prompt"
            system_prompt = "You are a helpful assistant"

            llm.generate(prompt, system_prompt=system_prompt)

            # Check messages include system prompt
            messages = mock_completion.call_args[1]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == system_prompt

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
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

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west1"},
            clear=True,
        ):
            llm = VertexAILLM()
            prompt = "Test prompt"

            llm.generate(prompt, temperature=0.7, max_tokens=100)

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 100
            assert call_kwargs["vertex_ai_project"] == "test-project"
            assert call_kwargs["vertex_ai_location"] == "europe-west1"

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_init_does_not_modify_credentials_env_var(self, mock_completion):
        """Test that init does not modify GOOGLE_APPLICATION_CREDENTIALS.

        Credentials are passed in-memory via vertex_credentials, so
        the env var should remain untouched.
        """
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

        with patch.dict(
            os.environ,
            {
                "GOOGLE_APPLICATION_CREDENTIALS": encoded_creds,
                "VERTEX_AI_LOCATION": "asia-northeast1",
            },
            clear=True,
        ):
            llm = VertexAILLM(credentials=encoded_creds, location="asia-northeast1")

            assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == encoded_creds

            llm.generate("Test prompt")

            call_kwargs = mock_completion.call_args[1]
            creds_sent = json.loads(call_kwargs["vertex_credentials"])
            assert creds_sent["project_id"] == "test-project"


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

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM(model_name="gemini-2.0-flash")
            config = llm.get_config_info()

            assert config["provider"] == "vertex_ai"
            assert config["model"] == "vertex_ai/gemini-2.0-flash"
            assert config["project"] == "test-project"
            assert config["location"] == "europe-west3"
            assert config["credentials_source"] == "base64"

    def test_get_config_info_file_credentials(self):
        """Test get_config_info returns correct information for file credentials."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(mock_creds, tf)
            temp_path = tf.name

        try:
            with patch.dict(
                os.environ,
                {"GOOGLE_APPLICATION_CREDENTIALS": temp_path, "VERTEX_AI_LOCATION": "us-central1"},
                clear=True,
            ):
                llm = VertexAILLM()
                config = llm.get_config_info()

                assert config["credentials_source"] == "file"
        finally:
            os.unlink(temp_path)


class TestVertexAIRegionalLocations:
    """Test different regional locations."""

    @pytest.mark.parametrize(
        "location",
        [
            "europe-west1",
            "europe-west3",
            "europe-west4",
            "us-central1",
            "us-east4",
            "asia-northeast1",
            "asia-southeast1",
        ],
    )
    def test_regional_locations(self, location):
        """Test that various regional locations are set correctly."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": location},
            clear=True,
        ):
            llm = VertexAILLM()
            assert llm.model["location"] == location


class TestVertexAICredentialSecurity:
    """Test credential security: error message masking, no disk writes."""

    def test_base64_credentials_not_written_to_disk(self):
        """Test that base64 credentials stay in memory (no temp files)."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()
            vertex_creds = llm.model["vertex_credentials"]
            assert json.loads(vertex_creds)["project_id"] == "test-project"
            assert llm.model["credentials_source"] == "base64"

    def test_error_message_does_not_leak_base64_credentials(self):
        """Test that base64 credential values are never included in error messages."""
        # A value that looks like base64 but is invalid JSON after decoding
        fake_secret = base64.b64encode(b"not-json-content-with-secret-key").decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": fake_secret, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            with pytest.raises(ValueError) as exc_info:
                VertexAILLM()
            # The raw base64 value must not appear in the error
            assert fake_secret not in str(exc_info.value)

    def test_error_message_shows_file_path_when_path_like(self):
        """Test that file-like paths are shown in error messages (they're not secrets)."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_APPLICATION_CREDENTIALS": "/etc/missing/creds.json",
                "VERTEX_AI_LOCATION": "europe-west3",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="/etc/missing/creds.json"):
                VertexAILLM()


class TestVertexAIGenerateStream:
    """Test generate_stream method functionality."""

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_stream_yields_chunks(self, mock_acompletion):
        """Test that generate_stream yields content chunks."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        # Create mock async iterator of chunks
        chunk1 = Mock()
        chunk1.choices = [Mock()]
        chunk1.choices[0].delta = Mock(content="Hello ")

        chunk2 = Mock()
        chunk2.choices = [Mock()]
        chunk2.choices[0].delta = Mock(content="world")

        chunk3 = Mock()
        chunk3.choices = [Mock()]
        chunk3.choices[0].delta = Mock(content=None)  # Final chunk with no content

        async def mock_stream():
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk

        mock_acompletion.return_value = mock_stream()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()

            async def run():
                chunks = []
                async for chunk in llm.generate_stream("Test prompt"):
                    chunks.append(chunk)
                return chunks

            result = asyncio.run(run())
            assert result == ["Hello ", "world"]

            # Verify vertex params were passed
            call_kwargs = mock_acompletion.call_args[1]
            assert call_kwargs["vertex_ai_project"] == "test-project"
            assert call_kwargs["vertex_ai_location"] == "europe-west3"
            assert call_kwargs["stream"] is True

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_stream_preserves_credentials_env_var(self, mock_acompletion):
        """Test that generate_stream does not alter GOOGLE_APPLICATION_CREDENTIALS."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        async def mock_stream():
            yield Mock(choices=[Mock(delta=Mock(content="hi"))])

        mock_acompletion.return_value = mock_stream()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM(credentials=encoded_creds, location="europe-west3")
            env_before = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

            async def run():
                async for _ in llm.generate_stream("Test"):
                    pass

            asyncio.run(run())
            assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == env_before


class TestVertexAIInMemoryCredentials:
    """Test that base64 credentials are handled entirely in memory."""

    def test_credentials_json_roundtrip(self):
        """Test that decoded credentials faithfully reproduce the original JSON."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "test@test.iam.gserviceaccount.com",
        }

        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm = VertexAILLM()
            roundtrip = json.loads(llm.model["vertex_credentials"])
            assert roundtrip == mock_creds

    def test_multiple_instances_share_same_json(self):
        """Test that two instances with the same credentials get identical JSON."""
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        encoded_creds = base64.b64encode(json.dumps(mock_creds).encode()).decode()

        with patch.dict(
            os.environ,
            {"GOOGLE_APPLICATION_CREDENTIALS": encoded_creds, "VERTEX_AI_LOCATION": "europe-west3"},
            clear=True,
        ):
            llm1 = VertexAILLM()
            llm2 = VertexAILLM()
            assert llm1.model["vertex_credentials"] == llm2.model["vertex_credentials"]
