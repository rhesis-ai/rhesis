"""
The test execution summary links the endpoint name to its page in the frontend.

It used to link to endpoint.url, the target of the system under test. In self-hosted
setups that is often cluster-internal, so the link was dead and leaked the address.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from rhesis.backend.jobs.execution.result_processor import get_test_context
from rhesis.backend.notifications.email.template_service import EmailTemplate, TemplateService
from tests.notifications.email_fixtures import FIXTURES, FRONTEND

TARGET_URL = "http://triage.ml.svc.cluster.local:4000/v1/chat/completions"


def _render(**overrides) -> str:
    variables = {**FIXTURES[EmailTemplate.TEST_EXECUTION_SUMMARY], **overrides}
    return TemplateService().render_template(EmailTemplate.TEST_EXECUTION_SUMMARY, variables)


@pytest.mark.unit
def test_endpoint_links_to_frontend_page():
    endpoint_id = FIXTURES[EmailTemplate.TEST_EXECUTION_SUMMARY]["endpoint_id"]
    html = _render(endpoint_url=TARGET_URL)

    assert f'href="{FRONTEND}/endpoints/{endpoint_id}"' in html
    assert TARGET_URL not in html


@pytest.mark.unit
def test_endpoint_without_id_is_not_linked():
    html = _render(endpoint_id=None)

    assert "triage-assistant-staging" in html
    assert "/endpoints/" not in html


@pytest.mark.unit
def test_get_test_context_returns_endpoint_id_not_url():
    endpoint_id = uuid4()
    config = SimpleNamespace(
        test_set=SimpleNamespace(name="Set"),
        endpoint=SimpleNamespace(
            id=endpoint_id,
            name="Endpoint",
            url=TARGET_URL,
            project=SimpleNamespace(name="Project"),
        ),
    )

    assert get_test_context(config) == ("Set", "Endpoint", str(endpoint_id), "Project")
