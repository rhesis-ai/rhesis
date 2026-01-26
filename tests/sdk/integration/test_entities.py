import pytest
from requests import HTTPError

from rhesis.sdk.entities.behavior import Behavior
from rhesis.sdk.entities.category import Category
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.project import Project
from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.entities.status import Status
from rhesis.sdk.entities.test_configuration import TestConfiguration
from rhesis.sdk.entities.test_run import TestRun
from rhesis.sdk.entities.topic import Topic

# ============================================================================
# Behavior Tests
# ============================================================================


def test_behavior(db_cleanup):
    behavior = Behavior(
        name="Test Behavior",
        description="Test Description",
    )

    result = behavior.push()

    assert result["id"] is not None
    assert result["name"] == "Test Behavior"
    assert result["description"] == "Test Description"


def test_behavior_push_pull(db_cleanup):
    behavior = Behavior(
        name="Test push pull behavior",
        description="Test push pull behavior description",
    )
    behavior.push()

    pulled_behavior = behavior.pull()

    assert pulled_behavior.name == "Test push pull behavior"
    assert pulled_behavior.description == "Test push pull behavior description"


def test_behavior_delete(db_cleanup):
    behavior = Behavior(
        name="Test push pull behavior",
        description="Test push pull behavior description",
    )

    behavior.push()
    behavior.delete()

    with pytest.raises(HTTPError):
        behavior.pull()


# ============================================================================
# Category Tests
# ============================================================================


def test_category(db_cleanup):
    category = Category(
        name="Test Category",
        description="Test Category Description",
    )

    result = category.push()

    assert result["id"] is not None
    assert result["name"] == "Test Category"
    assert result["description"] == "Test Category Description"


def test_category_push_pull(db_cleanup):
    category = Category(
        name="Test push pull category",
        description="Test push pull category description",
    )
    category.push()

    pulled_category = category.pull()

    assert pulled_category.name == "Test push pull category"
    assert pulled_category.description == "Test push pull category description"


def test_category_delete(db_cleanup):
    category = Category(
        name="Test category to delete",
        description="Test category to delete description",
    )

    category.push()
    category.delete()

    with pytest.raises(HTTPError):
        category.pull()


# ============================================================================
# Topic Tests
# ============================================================================


def test_topic(db_cleanup):
    topic = Topic(
        name="Test Topic",
        description="Test Topic Description",
    )

    result = topic.push()

    assert result["id"] is not None
    assert result["name"] == "Test Topic"
    assert result["description"] == "Test Topic Description"


def test_topic_push_pull(db_cleanup):
    topic = Topic(
        name="Test push pull topic",
        description="Test push pull topic description",
    )
    topic.push()

    pulled_topic = topic.pull()

    assert pulled_topic.name == "Test push pull topic"
    assert pulled_topic.description == "Test push pull topic description"


def test_topic_delete(db_cleanup):
    topic = Topic(
        name="Test topic to delete",
        description="Test topic to delete description",
    )

    topic.push()
    topic.delete()

    with pytest.raises(HTTPError):
        topic.pull()


# ============================================================================
# Prompt Tests
# ============================================================================


def test_prompt(db_cleanup):
    prompt = Prompt(
        content="Test prompt content",
        language_code="en",
    )

    result = prompt.push()

    assert result["id"] is not None
    assert result["content"] == "Test prompt content"
    assert result["language_code"] == "en"


def test_prompt_push_pull(db_cleanup):
    prompt = Prompt(
        content="Test push pull prompt content",
        language_code="en",
    )
    prompt.push()

    pulled_prompt = prompt.pull()

    assert pulled_prompt.content == "Test push pull prompt content"
    assert pulled_prompt.language_code == "en"


def test_prompt_delete(db_cleanup):
    prompt = Prompt(
        content="Test prompt to delete",
        language_code="en",
    )

    prompt.push()
    prompt.delete()

    with pytest.raises(HTTPError):
        prompt.pull()


# ============================================================================
# Project Tests
# ============================================================================


def test_project(db_cleanup):
    project = Project(
        name="Test Project",
        description="Test Project Description",
    )

    result = project.push()

    assert result["id"] is not None
    assert result["name"] == "Test Project"
    assert result["description"] == "Test Project Description"


def test_project_push_pull(db_cleanup):
    project = Project(
        name="Test push pull project",
        description="Test push pull project description",
    )
    project.push()

    pulled_project = project.pull()

    assert pulled_project.name == "Test push pull project"
    assert pulled_project.description == "Test push pull project description"


def test_project_delete(db_cleanup):
    project = Project(
        name="Test project to delete",
        description="Test project to delete description",
    )

    project.push()
    project.delete()

    with pytest.raises(HTTPError):
        project.pull()


# ============================================================================
# Status Tests
# ============================================================================


def test_status(db_cleanup):
    status = Status(
        name="Test Status",
        description="Test Status Description",
    )

    result = status.push()

    assert result["id"] is not None
    assert result["name"] == "Test Status"
    assert result["description"] == "Test Status Description"


def test_status_push_pull(db_cleanup):
    status = Status(
        name="Test push pull status",
        description="Test push pull status description",
    )
    status.push()

    pulled_status = status.pull()

    assert pulled_status.name == "Test push pull status"
    assert pulled_status.description == "Test push pull status description"


def test_status_delete(db_cleanup):
    status = Status(
        name="Test status to delete",
        description="Test status to delete description",
    )

    status.push()
    status.delete()

    with pytest.raises(HTTPError):
        status.pull()


# ============================================================================
# Endpoint Tests
# ============================================================================


def test_endpoint(db_cleanup):
    """Test creating an endpoint with all configuration fields."""
    endpoint = Endpoint(
        name="Test Endpoint",
        description="Test Endpoint Description",
        connection_type="REST",
        url="https://api.example.com/test",
        project_id="12340000-0000-4000-8000-000000001234",
        method="POST",
        endpoint_path="/v1/chat",
        request_headers={"Content-Type": "application/json"},
        query_params={"api_version": "2024-01"},
        request_mapping={"message": "{{ input }}"},
        response_mapping={"output": "result.text"},
        auth_token="sk-test-token",
    )

    result = endpoint.push()

    # Basic fields
    assert result["id"] is not None
    assert result["name"] == "Test Endpoint"
    assert result["description"] == "Test Endpoint Description"
    assert result["connection_type"] == "REST"
    assert result["url"] == "https://api.example.com/test"
    # New fields
    assert result["method"] == "POST"
    assert result["endpoint_path"] == "/v1/chat"
    assert result["request_headers"] == {"Content-Type": "application/json"}
    assert result["query_params"] == {"api_version": "2024-01"}
    assert result["request_mapping"] == {"message": "{{ input }}"}
    assert result["response_mapping"] == {"output": "result.text"}


def test_endpoint_push_pull(db_cleanup):
    """Test push/pull cycle preserves all endpoint fields."""
    endpoint = Endpoint(
        name="Test push pull endpoint",
        description="Test push pull endpoint description",
        connection_type="REST",
        url="https://api.example.com/push-pull",
        project_id="12340000-0000-4000-8000-000000001234",
        method="POST",
        endpoint_path="/v1/completions",
        request_headers={"Content-Type": "application/json", "X-Api-Version": "2"},
        query_params={"stream": "false"},
        request_mapping={"prompt": "{{ input }}", "max_tokens": 100},
        response_mapping={"output": "choices[0].text"},
        auth_token="sk-push-pull-test-token",
    )
    endpoint.push()

    pulled_endpoint = endpoint.pull()

    # Basic fields
    assert pulled_endpoint.name == "Test push pull endpoint"
    assert pulled_endpoint.description == "Test push pull endpoint description"
    assert pulled_endpoint.connection_type == "REST"
    assert pulled_endpoint.url == "https://api.example.com/push-pull"
    # New fields
    assert pulled_endpoint.method == "POST"
    assert pulled_endpoint.endpoint_path == "/v1/completions"
    assert pulled_endpoint.request_headers == {
        "Content-Type": "application/json",
        "X-Api-Version": "2",
    }
    assert pulled_endpoint.query_params == {"stream": "false"}
    assert pulled_endpoint.request_mapping == {"prompt": "{{ input }}", "max_tokens": 100}
    assert pulled_endpoint.response_mapping == {"output": "choices[0].text"}


def test_endpoint_delete(db_cleanup):
    endpoint = Endpoint(
        name="Test endpoint to delete",
        description="Test endpoint to delete description",
        connection_type="REST",
        url="https://api.example.com/delete",
        project_id="12340000-0000-4000-8000-000000001234",
    )

    endpoint.push()
    endpoint.delete()

    with pytest.raises(HTTPError):
        endpoint.pull()


def test_endpoint_with_all_fields(db_cleanup):
    """Test creating an endpoint with all configuration fields and verifying persistence."""
    endpoint = Endpoint(
        name="Test Endpoint Full Config",
        description="Endpoint with all configuration fields",
        connection_type="REST",
        url="https://api.openai.com",
        project_id="12340000-0000-4000-8000-000000001234",
        method="POST",
        endpoint_path="/v1/chat/completions",
        request_headers={"Content-Type": "application/json"},
        query_params={"version": "v1"},
        request_mapping={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "{{ input }}"}],
        },
        response_mapping={"output": "choices[0].message.content"},
        auth_token="sk-test-token",
    )

    result = endpoint.push()

    # Verify push response
    assert result["id"] is not None
    assert result["name"] == "Test Endpoint Full Config"
    assert result["method"] == "POST"
    assert result["endpoint_path"] == "/v1/chat/completions"
    assert result["request_headers"] == {"Content-Type": "application/json"}
    assert result["query_params"] == {"version": "v1"}
    assert result["request_mapping"]["model"] == "gpt-4"
    assert result["response_mapping"]["output"] == "choices[0].message.content"

    # Verify fields persist after pull
    pulled = endpoint.pull()
    assert pulled.request_mapping["model"] == "gpt-4"
    assert pulled.response_mapping["output"] == "choices[0].message.content"
    assert pulled.request_headers == {"Content-Type": "application/json"}


def test_endpoint_update_mappings(db_cleanup):
    """Test updating mapping fields on an existing endpoint."""
    endpoint = Endpoint(
        name="Test Update Mappings",
        connection_type="REST",
        url="https://api.example.com/chat",
        project_id="12340000-0000-4000-8000-000000001234",
        request_mapping={"original": "mapping"},
    )
    endpoint.push()

    # Update the mapping
    endpoint.request_mapping = {"updated": "mapping"}
    endpoint.response_mapping = {"new": "response"}
    result = endpoint.push()

    assert result["request_mapping"] == {"updated": "mapping"}
    assert result["response_mapping"] == {"new": "response"}


def test_endpoint_required_fields_validation():
    """Test that push fails without required fields."""
    # Missing name
    endpoint = Endpoint(
        connection_type="REST",
        project_id="12340000-0000-4000-8000-000000001234",
    )
    with pytest.raises(ValueError, match="name"):
        endpoint.push()

    # Missing connection_type
    endpoint = Endpoint(
        name="Test",
        project_id="12340000-0000-4000-8000-000000001234",
    )
    with pytest.raises(ValueError, match="connection_type"):
        endpoint.push()

    # Missing project_id
    endpoint = Endpoint(
        name="Test",
        connection_type="REST",
    )
    with pytest.raises(ValueError, match="project_id"):
        endpoint.push()


# ============================================================================
# TestRun Tests (requires Endpoint and TestConfiguration)
# ============================================================================


def test_test_run(db_cleanup):
    # Create endpoint first (required for test configuration)
    endpoint = Endpoint(
        name="Test Endpoint for TestRun",
        description="Test Endpoint Description",
        connection_type="REST",
        url="https://example.com/api",
        project_id="12340000-0000-4000-8000-000000001234",
    )
    endpoint.push()

    # Create test configuration (required for test run)
    test_config = TestConfiguration(
        endpoint_id=endpoint.id,
    )
    test_config.push()

    # Create test run
    test_run = TestRun(
        test_configuration_id=test_config.id,
        name="Test Run",
    )

    result = test_run.push()

    assert result["id"] is not None
    assert result["test_configuration_id"] == test_config.id
    assert result["name"] == "Test Run"


def test_test_run_push_pull(db_cleanup):
    # Create endpoint first
    endpoint = Endpoint(
        name="Test Endpoint for TestRun Push Pull",
        description="Test Endpoint Description",
        connection_type="REST",
        url="https://example.com/api",
        project_id="12340000-0000-4000-8000-000000001234",
    )
    endpoint.push()

    # Create test configuration
    test_config = TestConfiguration(
        endpoint_id=endpoint.id,
    )
    test_config.push()

    # Create test run
    test_run = TestRun(
        test_configuration_id=test_config.id,
        name="Test push pull test run",
    )
    test_run.push()

    pulled_test_run = test_run.pull()

    assert pulled_test_run.test_configuration_id == test_config.id
    assert pulled_test_run.name == "Test push pull test run"


def test_test_run_delete(db_cleanup):
    # Create endpoint first
    endpoint = Endpoint(
        name="Test Endpoint for TestRun Delete",
        description="Test Endpoint Description",
        connection_type="REST",
        url="https://example.com/api",
        project_id="12340000-0000-4000-8000-000000001234",
    )
    endpoint.push()

    # Create test configuration
    test_config = TestConfiguration(
        endpoint_id=endpoint.id,
    )
    test_config.push()

    # Create test run
    test_run = TestRun(
        test_configuration_id=test_config.id,
        name="Test run to delete",
    )

    test_run.push()
    test_run.delete()

    with pytest.raises(HTTPError):
        test_run.pull()


# ============================================================================
# Model Tests
# ============================================================================


def test_model(db_cleanup):
    """Test creating a model with API key."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Test OpenAI Model",
        description="Test model for integration tests",
        provider="openai",
        model_name="gpt-4",
        key="sk-test-api-key-12345",
    )

    result = model.push()

    assert result["id"] is not None
    assert result["name"] == "Test OpenAI Model"
    assert result["description"] == "Test model for integration tests"
    assert result["model_name"] == "gpt-4"


def test_model_push_pull(db_cleanup):
    """Test creating and retrieving a model."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Test push pull model",
        description="Test push pull model description",
        provider="anthropic",
        model_name="claude-3-sonnet-20240229",
        key="sk-ant-test-key-67890",
    )
    model.push()

    pulled_model = model.pull()

    assert pulled_model.name == "Test push pull model"
    assert pulled_model.description == "Test push pull model description"
    assert pulled_model.model_name == "claude-3-sonnet-20240229"


def test_model_delete(db_cleanup):
    """Test deleting a model."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Test model to delete",
        description="Test model to delete description",
        provider="openai",
        model_name="gpt-3.5-turbo",
        key="sk-delete-test-key",
    )

    model.push()
    model.delete()

    with pytest.raises(HTTPError):
        model.pull()


def test_model_update(db_cleanup):
    """Test updating a model."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Test model to update",
        description="Original description",
        provider="openai",
        model_name="gpt-4",
        key="sk-original-key",
    )
    model.push()

    # Update the model
    model.name = "Updated model name"
    model.description = "Updated description"
    model.model_name = "gpt-4-turbo"
    result = model.push()

    assert result["name"] == "Updated model name"
    assert result["description"] == "Updated description"
    assert result["model_name"] == "gpt-4-turbo"


def test_model_with_different_providers(db_cleanup):
    """Test creating models with different providers."""
    from rhesis.sdk.entities.model import Model

    providers_and_models = [
        ("openai", "gpt-4", "sk-openai-test"),
        ("anthropic", "claude-3-opus-20240229", "sk-ant-test"),
        ("gemini", "gemini-pro", "AIza-test-key"),
    ]

    for provider, model_name, api_key in providers_and_models:
        model = Model(
            name=f"Test {provider.title()} Model",
            provider=provider,
            model_name=model_name,
            key=api_key,
        )

        result = model.push()

        assert result["id"] is not None
        assert result["model_name"] == model_name


def test_model_set_default_generation(db_cleanup):
    """Test setting a model as default for generation."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Default Generation Model",
        description="Model for test generation",
        provider="openai",
        model_name="gpt-4",
        key="sk-gen-default-key",
    )
    model.push()

    # Should not raise an exception
    model.set_default_generation()

    # Verify by checking model has an ID (was saved)
    assert model.id is not None


def test_model_set_default_evaluation(db_cleanup):
    """Test setting a model as default for evaluation."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Default Evaluation Model",
        description="Model for LLM-as-judge evaluation",
        provider="anthropic",
        model_name="claude-3-sonnet-20240229",
        key="sk-eval-default-key",
    )
    model.push()

    # Should not raise an exception
    model.set_default_evaluation()

    # Verify by checking model has an ID (was saved)
    assert model.id is not None


def test_model_set_default_without_push_raises_error(db_cleanup):
    """Test that setting default without pushing first raises an error."""
    from rhesis.sdk.entities.model import Model

    model = Model(
        name="Unsaved Model",
        provider="openai",
        model_name="gpt-4",
        key="sk-unsaved-key",
    )

    # Should raise ValueError because model hasn't been pushed
    with pytest.raises(ValueError, match="Model must be saved"):
        model.set_default_generation()

    with pytest.raises(ValueError, match="Model must be saved"):
        model.set_default_evaluation()


def test_models_collection_all(db_cleanup):
    """Test listing all models via collection."""
    from rhesis.sdk.entities.model import Model, Models

    # Create a few models
    for i in range(3):
        model = Model(
            name=f"Collection Test Model {i}",
            provider="openai",
            model_name=f"gpt-4-test-{i}",
            key=f"sk-collection-test-{i}",
        )
        model.push()

    # Get all models
    all_models = Models.all()

    # Should have at least 3 models (might have more from other tests)
    assert len(all_models) >= 3


def test_models_collection_pull_by_name(db_cleanup):
    """Test pulling a model by name via collection."""
    from rhesis.sdk.entities.model import Model, Models

    unique_name = "Unique Model Name For Pull Test"
    model = Model(
        name=unique_name,
        provider="openai",
        model_name="gpt-4",
        key="sk-pull-by-name-test",
    )
    model.push()

    # Pull by name
    pulled_model = Models.pull(name=unique_name)

    assert pulled_model.name == unique_name
    assert pulled_model.model_name == "gpt-4"
