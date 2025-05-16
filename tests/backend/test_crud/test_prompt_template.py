import pytest
from rhesis.app.schemas import PromptTemplateCreate, PromptTemplateUpdate
from rhesis.tests.mock import generate_mock_data  # Import the mock data generator

@pytest.fixture
def test_prompt_template_data():
    return generate_mock_data(PromptTemplateCreate)

@pytest.fixture
def test_prompt_template(client, test_prompt_template_data):

    response = client.post(
        "/prompt_templates/",
        json=test_prompt_template_data,
    )

    return response.json()

def test_create_prompt_template(client, test_prompt_template_data):

    response = client.post(
        "/prompt_templates/",
        json=test_prompt_template_data,
    )
    assert response.status_code == 200
    assert response.json()["content"] == test_prompt_template_data["content"]


def test_read_prompt_templates(client):
    response = client.get("/prompt_templates/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_read_prompt_template(client, test_prompt_template):

    # Read the created prompt_template
    prompt_template_id = test_prompt_template["id"]
    response = client.get(f"/prompt_templates/{prompt_template_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == test_prompt_template["content"]


def test_update_prompt_template(client, test_prompt_template):

    # Update the prompt_template
    prompt_template_id = test_prompt_template["id"]

    prompt_template_data_update = generate_mock_data(PromptTemplateUpdate)
    prompt_template_data_update = {
        key: value for key, value in prompt_template_data_update.items() if value is not None
    }

    response = client.put(
        f"/prompt_templates/{prompt_template_id}",
        json=prompt_template_data_update,
    )

    # Now, check if the prompt_template is updated
    assert response.status_code == 200

    for key, value in prompt_template_data_update.items():
        assert response.json()[key] == value

def test_delete_prompt_template(client, test_prompt_template):

    # Delete the created prompt_template
    prompt_template_id = test_prompt_template["id"]

    response = client.delete(f"/prompt_templates/{prompt_template_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == test_prompt_template["content"]



