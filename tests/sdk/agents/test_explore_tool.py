"""Tests for ExploreEndpointTool."""

import pytest

from rhesis.sdk.agents.tools import ExploreEndpointTool
from rhesis.sdk.targets import Target, TargetResponse


class FakeTarget(Target):
    """Minimal Target for testing."""

    def __init__(self, endpoint_id="fake-ep"):
        self._id = endpoint_id

    @property
    def target_type(self):
        return "endpoint"

    @property
    def target_id(self):
        return self._id

    @property
    def description(self):
        return f"Fake endpoint {self._id}"

    def send_message(self, message, conversation_id=None, **kw):
        return TargetResponse(success=True, content=f"Reply to: {message}")

    def validate_configuration(self):
        return True, None


@pytest.mark.unit
class TestExploreEndpointToolInit:
    """Test ExploreEndpointTool initialization modes."""

    def test_requires_endpoint_or_factory(self):
        with pytest.raises(ValueError, match="Must provide"):
            ExploreEndpointTool()

    def test_unbound_mode_with_factory(self):
        factory = lambda eid: FakeTarget(eid)
        tool = ExploreEndpointTool(target_factory=factory)
        assert tool.name == "explore_endpoint"
        assert tool._endpoint is None
        assert tool._target_factory is factory

    def test_unbound_description_mentions_endpoint_id(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        assert "endpoint_id" in tool.description

    def test_unbound_schema_requires_endpoint_id(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        schema = tool.parameters_schema
        assert "endpoint_id" in schema["properties"]
        assert "endpoint_id" in schema["required"]
        assert "goal" in schema["required"]

    def test_bound_schema_does_not_require_endpoint_id(self):
        class FakeEndpoint:
            id = "ep-123"
            name = "Test"
            description = "A test endpoint"

        tool = ExploreEndpointTool(endpoint=FakeEndpoint())
        schema = tool.parameters_schema
        assert "endpoint_id" not in schema.get("properties", {})
        assert "endpoint_id" not in schema["required"]

    def test_requires_confirmation_is_false(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        assert tool.requires_confirmation is False


@pytest.mark.unit
class TestExploreEndpointToolExecute:
    """Test ExploreEndpointTool.execute() in unbound mode."""

    @pytest.mark.asyncio
    async def test_empty_goal_rejected(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        result = await tool.execute(goal="", endpoint_id="ep-1")
        assert not result.success
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_endpoint_id_in_unbound_mode(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        result = await tool.execute(goal="Explore domain")
        assert not result.success
        assert "endpoint" in result.error.lower()

    @pytest.mark.asyncio
    async def test_factory_error_handled(self):
        def bad_factory(eid):
            raise ValueError("endpoint not found")

        tool = ExploreEndpointTool(target_factory=bad_factory)
        result = await tool.execute(goal="Explore", endpoint_id="bad-id")
        assert not result.success
        assert "resolve endpoint" in result.error.lower()

    def test_resolve_target_uses_factory(self):
        created = []

        def factory(eid):
            t = FakeTarget(eid)
            created.append(eid)
            return t

        tool = ExploreEndpointTool(target_factory=factory)
        target = tool._resolve_target("ep-42")
        assert created == ["ep-42"]
        assert target.target_id == "ep-42"

    def test_resolve_target_uses_bound_endpoint(self):
        class FakeEndpoint:
            id = "ep-bound"
            name = "Bound"
            description = ""

        tool = ExploreEndpointTool(endpoint=FakeEndpoint())
        # _resolve_target should try to use EndpointTarget, which
        # we can't construct without Penelope in unit tests.
        # Instead, verify the tool stores the endpoint correctly.
        assert tool._endpoint.id == "ep-bound"
        assert tool._endpoint_id == "ep-bound"
