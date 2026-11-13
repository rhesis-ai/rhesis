"""A tenant model is only unmetered when it runs on the tenant's own credential.

``metered=False`` means "the org pays its provider directly". That is only
true when the credential the SDK provider class consumes came from the row:
every provider falls back to this server's environment otherwise
(``GOOGLE_APPLICATION_CREDENTIALS`` for Vertex, which ignores ``api_key``
entirely; ``OPENAI_API_KEY`` etc. for providers that ignore ``api_base``).

Also covers the routes that used to hand the default-model string straight
to an SDK class, which built an unstamped model past the MODEL_TOKENS gate.
"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict
from rhesis.backend.app.utils.model_credentials import has_own_credentials
from rhesis.backend.app.utils.model_errors import ModelConfigurationError


def _service_account(project: str, email: str) -> dict:
    # Shape-only stand-in; no real key material, and nothing here reaches Google.
    return {
        "type": "service_account",
        "project_id": project,
        "private_key_id": "0",
        "private_key": "-----BEGIN PRIVATE KEY-----\nnot-a-key\n-----END PRIVATE KEY-----\n",
        "client_email": email,
    }


PLATFORM_SA = _service_account("platform-project", "platform@platform-project.iam")
TENANT_SA = _service_account("tenant-project", "tenant@tenant-project.iam")


def _b64(info: dict) -> str:
    return base64.b64encode(json.dumps(info).encode()).decode()


@pytest.fixture
def platform_env(monkeypatch):
    """The credentials a deployment carries in its own environment."""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", _b64(PLATFORM_SA))
    monkeypatch.setenv("VERTEX_AI_LOCATION", "europe-west4")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-platform")
    monkeypatch.setenv("GEMINI_API_KEY", "platform-gemini")


def _row(provider: str, key: str = "", endpoint=None, model_name="gemini-2.5-flash"):
    return SimpleNamespace(
        name="tenant-model",
        model_name=model_name,
        key=key,
        endpoint=endpoint,
        model_type="language",
        provider_type=SimpleNamespace(type_value=provider),
    )


def _resolve(monkeypatch, row):
    """Run *row* through the real resolver and the real SDK factory."""
    from rhesis.backend.app.utils import user_model_utils

    monkeypatch.setattr(user_model_utils, "_load_model_row", lambda db, mid, org: row)
    return user_model_utils._fetch_and_configure_model(
        MagicMock(), "model-1", "org-1", "rhesis/default"
    )


class TestVertexCredential:
    @pytest.mark.parametrize("key", ["x", "", "not-json", _b64({"type": "authorized_user"})])
    def test_a_key_vertex_cannot_use_is_not_own_credentials(self, key):
        assert has_own_credentials("vertex_ai", key, None) is False

    def test_a_file_path_is_not_own_credentials(self, tmp_path):
        """The SDK would read it from this server, where our own credentials live."""
        path = tmp_path / "sa.json"
        path.write_text(json.dumps(PLATFORM_SA))
        assert has_own_credentials("vertex_ai", str(path), None) is False

    @pytest.mark.parametrize("key", [json.dumps(TENANT_SA), _b64(TENANT_SA)])
    def test_a_service_account_is_own_credentials(self, key):
        assert has_own_credentials("vertex_ai", key, None) is True

    def test_tenant_row_with_bogus_key_is_refused_not_run_on_platform_creds(
        self, monkeypatch, platform_env
    ):
        with patch("rhesis.backend.app.utils.user_model_utils.get_model") as build:
            with pytest.raises(ModelConfigurationError, match="service-account"):
                _resolve(monkeypatch, _row("vertex_ai", key="x"))
        build.assert_not_called()

    def test_tenant_row_runs_on_its_own_service_account_unmetered(self, monkeypatch, platform_env):
        model = _resolve(monkeypatch, _row("vertex_ai", key=json.dumps(TENANT_SA)))

        assert model.usage_metered is False
        assert model.model["project"] == "tenant-project"
        used = json.loads(base64.b64decode(model._original_credentials_env))
        assert used["client_email"] == TENANT_SA["client_email"]


class TestKeyedProviders:
    @pytest.mark.parametrize("provider", ["openai", "gemini", "anthropic", "jev", "azure"])
    def test_an_endpoint_does_not_stand_in_for_the_key(self, provider):
        """These classes ignore ``api_base`` for auth and read the env key instead."""
        assert has_own_credentials(provider, "", "http://anything.example") is False

    @pytest.mark.parametrize("provider", ["vllm", "ollama", "litellm_proxy"])
    def test_self_hosted_providers_may_rely_on_the_endpoint(self, provider):
        assert has_own_credentials(provider, "", "http://vllm.internal:8000") is True
        assert has_own_credentials(provider, "tenant-key", None) is False

    def test_openai_row_with_only_an_endpoint_is_refused(self, monkeypatch, platform_env):
        with pytest.raises(ModelConfigurationError, match="needs an API key"):
            _resolve(
                monkeypatch, _row("openai", endpoint="http://anything.example", model_name="gpt-4o")
            )


class TestBedrock:
    @pytest.fixture
    def server_aws(self, monkeypatch):
        """AWS credentials LiteLLM would sign with if the row brought no Bedrock key."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAPLATFORM")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "platform-secret")
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

    def test_a_regional_endpoint_does_not_stand_in_for_the_key(self, monkeypatch, server_aws):
        with pytest.raises(ModelConfigurationError, match="needs an API key"):
            _resolve(
                monkeypatch,
                _row(
                    "bedrock",
                    endpoint="https://bedrock-runtime.eu-central-1.amazonaws.com",
                    model_name="eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
                ),
            )

    def test_tenant_row_runs_on_its_bedrock_key_and_region(self, monkeypatch, server_aws):
        endpoint = "https://bedrock-runtime.eu-central-1.amazonaws.com"
        model = _resolve(
            monkeypatch,
            _row(
                "bedrock",
                key="tenant-bedrock-key",
                endpoint=endpoint,
                model_name="eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
        )

        assert model.usage_metered is False
        assert model.api_key == "tenant-bedrock-key"
        assert model.api_base == endpoint
        assert model.model_name == "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"


class TestSelfHostedProviders:
    @pytest.fixture
    def server_keys(self, monkeypatch):
        monkeypatch.setenv("HOSTED_VLLM_API_KEY", "platform-vllm-key")
        monkeypatch.setenv("LITELLM_PROXY_API_KEY", "platform-proxy-key")

    def test_keyless_vllm_row_does_not_send_our_env_key(self, monkeypatch, server_keys):
        model = _resolve(
            monkeypatch, _row("vllm", endpoint="http://tenant.example:8000", model_name="m")
        )

        assert model.api_key != "platform-vllm-key"
        assert model.api_base == "http://tenant.example:8000"

    def test_keyless_proxy_row_does_not_send_our_env_key(self, monkeypatch, server_keys):
        model = _resolve(
            monkeypatch,
            _row("litellm_proxy", endpoint="http://tenant.example:4000", model_name="m"),
        )

        assert "platform-proxy-key" not in model._build_headers().get("Authorization", "")

    def test_the_tenant_key_is_still_sent(self, monkeypatch, server_keys):
        model = _resolve(
            monkeypatch,
            _row("vllm", key="tenant-key", endpoint="http://tenant.example:8000", model_name="m"),
        )

        assert model.api_key == "tenant-key"

    def test_a_key_without_an_endpoint_is_refused(self, monkeypatch, server_keys):
        """No endpoint means our own env or localhost base, not the tenant's server."""
        with pytest.raises(ModelConfigurationError, match="needs an endpoint"):
            _resolve(monkeypatch, _row("vllm", key="tenant-key", model_name="m"))


class TestInProcessProviders:
    @pytest.mark.parametrize("provider", ["huggingface", "lmformatenforcer"])
    def test_no_endpoint_makes_an_in_process_provider_the_tenants(self, provider):
        """These load the model inside this server and never use the row's endpoint."""
        assert has_own_credentials(provider, "", "http://tenant.example") is False

    def test_a_huggingface_row_gets_a_configuration_error_not_a_crash(self, monkeypatch):
        with pytest.raises(ModelConfigurationError, match="inside the Rhesis server"):
            _resolve(monkeypatch, _row("huggingface", endpoint="http://tenant.example"))


class TestConstructorMismatch:
    def test_an_unexpected_kwarg_is_a_configuration_error(self, monkeypatch):
        """A provider class that rejects a kwarg must not surface as a 500."""

        def _reject(**kwargs):
            raise TypeError("__init__() got an unexpected keyword argument 'api_key'")

        monkeypatch.setattr("rhesis.backend.app.utils.user_model_utils.get_model", _reject)
        with pytest.raises(ModelConfigurationError, match="Failed to initialize"):
            _resolve(monkeypatch, _row("openai", key="sk-tenant", model_name="gpt-4o"))

    async def test_connection_test_reports_it_as_a_configuration_error(self):
        from rhesis.backend.app.services.model_connection import ModelConnectionService

        with patch(
            "rhesis.sdk.models.factory.get_model",
            side_effect=TypeError("__init__() got an unexpected keyword argument 'api_base'"),
        ):
            result = await ModelConnectionService.test_connection(
                provider="openai", model_name="gpt-4o", api_key="sk-tenant"
            )

        assert result.success is False
        assert result.message.startswith("Configuration error")


@pytest.mark.integration
class TestConnectionTest:
    def test_vertex_with_a_bogus_key_does_not_succeed_on_platform_credentials(
        self, authenticated_client, platform_env
    ):
        # Would answer for any model built, so a success here means the platform creds ran.
        with patch(
            "rhesis.sdk.models.providers.litellm.LiteLLM.a_generate",
            new=AsyncMock(return_value="OK"),
        ):
            response = authenticated_client.post(
                "/models/test-connection",
                json={"provider": "vertex_ai", "model_name": "gemini-2.5-flash", "api_key": "x"},
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["success"] is False
        assert "service-account" in body["message"]

    def test_openai_with_no_key_does_not_succeed_on_platform_credentials(
        self, authenticated_client, platform_env
    ):
        with patch(
            "rhesis.sdk.models.providers.litellm.LiteLLM.a_generate",
            new=AsyncMock(return_value="OK"),
        ):
            response = authenticated_client.post(
                "/models/test-connection",
                json={
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "api_key": "",
                    "endpoint": "http://anything.example",
                },
            )

        assert response.json()["success"] is False


def _blocked(db, organization_id):
    raise QuotaExceededError(
        QuotaVerdict(
            resource=QuotaResource.MODEL_TOKENS,
            used=10,
            limit=10,
            allowed=False,
            over_limit=True,
            kind="flow",
            period_end="2030-01-31",
        )
    )


@pytest.mark.integration
class TestDefaultModelRoutesAreGated:
    @pytest.fixture
    def tokens_exhausted(self, monkeypatch):
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils._enforce_model_token_quota", _blocked
        )

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_metric_generate_returns_402_at_the_token_ceiling(
        self, generate, authenticated_client, tokens_exhausted
    ):
        response = authenticated_client.post("/metrics/generate", json={"prompt": "accuracy"})

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        assert response.json()["resource"] == QuotaResource.MODEL_TOKENS.value
        generate.assert_not_called()

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.improve")
    def test_metric_improve_returns_402_at_the_token_ceiling(
        self, improve, authenticated_client, tokens_exhausted
    ):
        response = authenticated_client.post(
            "/metrics/00000000-0000-0000-0000-000000000001/improve", json={"prompt": "stricter"}
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
        improve.assert_not_called()


class TestMcpAgentModel:
    async def test_the_agent_gets_the_gated_default_model(self):
        from rhesis.backend.app.services.tool.mcp import operations

        built = SimpleNamespace(model_name="default")
        result = SimpleNamespace(model_dump=lambda: {"success": True})
        with (
            patch.object(operations, "get_db_with_tenant_variables") as db_factory,
            patch.object(operations, "resolve_default_hosted_model", return_value=built) as resolve,
            patch.object(operations, "MCPAgent") as agent_cls,
        ):
            agent_cls.return_value.run_async = AsyncMock(return_value=result)
            await operations._run_agent(
                MagicMock(), "q", "sys", 3, "mcp-query", organization_id="org-1", user_id="u-1"
            )

        assert resolve.call_args.args[2] == "org-1"
        assert agent_cls.call_args.kwargs["model"] is built
        db_factory.assert_called_once_with("org-1", "u-1", "")

    async def test_the_agent_does_not_run_past_the_token_ceiling(self):
        from rhesis.backend.app.services.tool.mcp import operations

        with (
            patch.object(operations, "get_db_with_tenant_variables"),
            patch.object(
                operations,
                "resolve_default_hosted_model",
                side_effect=lambda *a: _blocked(None, None),
            ),
            patch.object(operations, "MCPAgent") as agent_cls,
        ):
            with pytest.raises(QuotaExceededError):
                await operations._run_agent(
                    MagicMock(), "q", "sys", 3, "mcp-query", organization_id="org-1", user_id="u-1"
                )
        agent_cls.assert_not_called()
