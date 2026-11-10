"""Endpoint request/response mappings are tenant-written Jinja2 and must render sandboxed."""

import json
import re
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from jinja2.sandbox import ImmutableSandboxedEnvironment, SecurityError
from pydantic import BaseModel

from rhesis.backend.app.services.invokers.templating import ResponseMapper, TemplateRenderer

ESCAPE_PAYLOADS = [
    "{{ cycler.__init__.__globals__.os.name }}",
    "{{ cycler.__init__.__globals__ }}",
    "{{ ''.__class__.__mro__ }}",
    "{{ input.__class__.__base__.__subclasses__() }}",
    "{{ lipsum.__globals__['os'].getcwd() }}",
    "{{ joiner.__init__.__globals__.__builtins__ }}",
]


class _Model(BaseModel):
    text: str = "hi"


def _mock_http_client(payload: Dict[str, Any]) -> AsyncMock:
    http_response = Mock()
    http_response.status_code = 200
    http_response.json.return_value = payload
    http_response.raise_for_status = Mock()
    http_response.text = json.dumps(payload)
    http_response.headers = {}
    http_response.reason_phrase = "OK"
    client = AsyncMock()
    client.post = AsyncMock(return_value=http_response)
    client.is_closed = False
    return client


class TestRendererSandbox:
    def test_renderers_use_immutable_sandbox(self):
        assert isinstance(TemplateRenderer().env, ImmutableSandboxedEnvironment)
        assert isinstance(ResponseMapper().env, ImmutableSandboxedEnvironment)

    def test_invokers_never_build_an_unsandboxed_jinja_environment(self):
        invokers = (
            Path(__file__).resolve().parents[3]
            / "apps/backend/src/rhesis/backend/app/services/invokers"
        )
        unsafe = re.compile(
            r"\bfrom jinja2 import\b[^\n]*\b(Environment|Template)\b"
            r"|jinja2\.(Environment|Template)\("
        )
        offenders = [
            str(p.relative_to(invokers))
            for p in invokers.rglob("*.py")
            if unsafe.search(p.read_text(encoding="utf-8"))
        ]
        assert offenders == []

    @pytest.mark.parametrize("payload", ESCAPE_PAYLOADS)
    def test_request_mapping_refuses_escape(self, payload):
        with pytest.raises(SecurityError):
            TemplateRenderer().render({"q": payload}, {"input": "x"})

    @pytest.mark.parametrize("payload", ESCAPE_PAYLOADS)
    def test_response_mapping_refuses_escape(self, payload):
        result = ResponseMapper().map_response({"input": "x"}, {"output": payload})
        assert result["output"] is None

    def test_mutating_methods_are_refused(self):
        with pytest.raises(SecurityError):
            TemplateRenderer().render("{{ messages.append(1) }}", {"messages": []})

    def test_simple_reference_does_not_walk_dunder_attributes(self):
        """A bare ``{{ a.b }}`` reference is resolved by hand; it must not reach dunders."""
        context = {"model": _Model()}
        with pytest.raises(SecurityError):
            TemplateRenderer().render({"q": "{{ model.__init__.__globals__ }}"}, context)
        mapped = ResponseMapper().map_response(
            context, {"output": "{{ model.__init__.__globals__ }}"}
        )
        assert mapped["output"] is None

    def test_legitimate_templates_still_render(self):
        renderer = TemplateRenderer()
        rendered = renderer.render(
            {
                "query": "{{ input }}",
                "history": "{{ messages | tojson }}",
                "alias": "{{ messages | to_json }}",
                "upper": "{{ input | upper }}",
                "nested": "{{ meta.user_id }}",
                "dict_key": "{{ meta._id }}",
                "parsed": "{{ '{\"a\": 1}' | fromjson }}",
                "loop": (
                    "{% for m in messages %}{{ m.role }}"
                    "{% if not loop.last %},{% endif %}{% endfor %}"
                ),
            },
            {
                "input": "hi",
                "messages": [{"role": "user"}, {"role": "assistant"}],
                "meta": {"user_id": "u1", "_id": "i1"},
            },
        )
        assert rendered["query"] == "hi"
        assert rendered["history"] == [{"role": "user"}, {"role": "assistant"}]
        assert rendered["alias"] == rendered["history"]
        assert rendered["upper"] == "HI"
        assert rendered["nested"] == "u1"
        assert rendered["dict_key"] == "i1"
        assert rendered["parsed"] == {"a": 1}
        assert rendered["loop"] == "user,assistant"

        mapped = ResponseMapper().map_response(
            {"data": {"text": "out", "_id": "r1"}, "alt": None},
            {
                "output": "{{ data.text or alt }}",
                "via_jsonpath": "{{ jsonpath('$.data.text') }}",
                "dict_key": "{{ data._id }}",
                "plain": "$.data.text",
            },
        )
        assert mapped == {
            "output": "out",
            "via_jsonpath": "out",
            "dict_key": "r1",
            "plain": "out",
        }


@pytest.mark.integration
class TestEndpointTestRouteSandbox:
    """The same payloads through ``POST /endpoints/test``, the route that rendered them before."""

    def _post(self, client: TestClient, request_mapping: Dict[str, Any], http_client):
        config = {
            "connection_type": "REST",
            "url": "https://api.example.com/v1/echo",
            "method": "POST",
            "request_headers": {"Content-Type": "application/json"},
            "request_mapping": request_mapping,
            "response_mapping": {"output": "$.answer"},
            "auth_type": "bearer_token",
            "auth_token": "t",
            "input_data": {"input": "ping"},
        }
        with patch(
            "rhesis.backend.app.services.invokers.rest_invoker._get_http_client",
            return_value=http_client,
        ):
            return client.post("/endpoints/test", json=config)

    @pytest.mark.parametrize("payload", ESCAPE_PAYLOADS)
    def test_escape_is_refused_before_any_request(self, authenticated_client, payload):
        http_client = _mock_http_client({"answer": "pong"})
        response = self._post(authenticated_client, {"q": payload}, http_client)

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["error_type"] == "template_error"
        assert "posix" not in response.text
        http_client.post.assert_not_called()

    def test_legitimate_mapping_still_sends(self, authenticated_client):
        http_client = _mock_http_client({"answer": "pong"})
        response = self._post(
            authenticated_client, {"q": "{{ input | upper }}", "raw": "{{ input }}"}, http_client
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["output"] == "pong"
        assert http_client.post.call_args.kwargs["json"] == {"q": "PING", "raw": "ping"}
