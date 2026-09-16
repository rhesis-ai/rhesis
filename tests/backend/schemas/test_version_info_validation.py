"""Tests for free-form version_info validation on endpoint schemas."""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.endpoint import Endpoint, EndpointCreate, EndpointUpdate
from rhesis.backend.app.schemas.validators import (
    VERSION_INFO_MAX_BYTES,
    VERSION_INFO_MAX_DEPTH,
    validate_version_info,
)


def _nested(depth: int) -> dict:
    """A dict nested exactly ``depth`` levels (depth 1 == {"k": "leaf"})."""
    node: dict = {"k": "leaf"}
    for _ in range(depth - 1):
        node = {"k": node}
    return node


class TestVersionInfoValidator:
    """The raw validator, independent of any schema."""

    def test_none_passes_through(self):
        assert validate_version_info(None) is None

    def test_empty_object_accepted(self):
        assert validate_version_info({}) == {}

    def test_nested_object_accepted(self):
        value = {"prompt_version": "v3.2", "cfg": {"temperature": 0.2}}
        assert validate_version_info(value) == value

    @pytest.mark.parametrize("value", [[1, 2, 3], "v3", 42, 1.5, True])
    def test_non_object_rejected(self, value):
        with pytest.raises(ValueError, match="must be a JSON object"):
            validate_version_info(value)

    def test_at_size_limit_accepted(self):
        # 'x' * n serializes to n + len('{"k": ""}') bytes.
        padding = "x" * (VERSION_INFO_MAX_BYTES - len('{"k": ""}'))
        value = {"k": padding}
        assert validate_version_info(value) == value

    def test_over_size_limit_rejected(self):
        padding = "x" * (VERSION_INFO_MAX_BYTES - len('{"k": ""}') + 1)
        with pytest.raises(ValueError, match="at most"):
            validate_version_info({"k": padding})

    def test_at_depth_limit_accepted(self):
        value = _nested(VERSION_INFO_MAX_DEPTH)
        assert validate_version_info(value) == value

    def test_over_depth_limit_rejected(self):
        with pytest.raises(ValueError, match="nest more than"):
            validate_version_info(_nested(VERSION_INFO_MAX_DEPTH + 1))

    def test_depth_counted_through_lists(self):
        with pytest.raises(ValueError, match="nest more than"):
            validate_version_info({"a": [[[[[[[["too deep"]]]]]]]]})

    def test_pathological_nesting_raises_value_error_not_recursion_error(self):
        """A hostile payload must surface as a 422, never a 500."""
        deep = current = {}
        for _ in range(100_000):
            current["n"] = {}
            current = current["n"]
        with pytest.raises(ValueError, match="nest more than"):
            validate_version_info(deep)


class TestVersionInfoOnEndpointSchemas:
    """Wiring into create/update/response schemas."""

    def test_create_accepts_object(self):
        ep = EndpointCreate(
            name="ep", connection_type="REST", version_info={"prompt_version": "v1"}
        )
        assert ep.version_info == {"prompt_version": "v1"}

    def test_create_defaults_to_none(self):
        assert EndpointCreate(name="ep", connection_type="REST").version_info is None

    def test_create_rejects_array(self):
        with pytest.raises(ValidationError, match="must be a JSON object"):
            EndpointCreate(name="ep", connection_type="REST", version_info=["v1"])

    def test_update_rejects_array(self):
        with pytest.raises(ValidationError, match="must be a JSON object"):
            EndpointUpdate(version_info=["v1"])

    def test_omitted_update_leaves_field_unset(self):
        """An omitted key must not clear a stored value -- crud uses exclude_unset."""
        assert "version_info" not in EndpointUpdate(name="x").model_dump(exclude_unset=True)

    def test_explicit_null_update_clears(self):
        dumped = EndpointUpdate(version_info=None).model_dump(exclude_unset=True)
        assert dumped == {"version_info": None}

    def test_response_schema_tolerates_oversize_legacy_row(self):
        """Reading must never fail on a row written before the limits existed."""
        legacy = {"k": "x" * (VERSION_INFO_MAX_BYTES * 2)}
        assert Endpoint.model_construct(version_info=legacy).version_info == legacy
