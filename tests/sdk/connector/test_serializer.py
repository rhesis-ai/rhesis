"""Unit tests for TypeSerializer."""

import dataclasses
from typing import NamedTuple

from pydantic import BaseModel

from rhesis.sdk.connector.serializer import TypeSerializer


# Test fixtures - Pydantic models
class PydanticModel(BaseModel):
    """Simple Pydantic model for testing."""

    name: str
    value: int


class NestedPydanticModel(BaseModel):
    """Pydantic model with nested model."""

    outer: str
    inner: PydanticModel


# Test fixtures - Dataclasses
@dataclasses.dataclass
class DataclassModel:
    """Simple dataclass for testing."""

    name: str
    value: int


@dataclasses.dataclass
class NestedDataclass:
    """Dataclass with nested dataclass."""

    outer: str
    inner: DataclassModel


# Test fixtures - Convention classes
class ConventionClass:
    """Class with to_dict/from_dict convention."""

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value

    def to_dict(self):
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


# Test fixtures - Named tuple
class PersonTuple(NamedTuple):
    """Named tuple for testing."""

    name: str
    age: int


# Test fixtures - Simple class (no special methods)
class SimpleClass:
    """Simple class with __init__ only."""

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value


class TestDump:
    """Test serialization (object → dict)."""

    def test_dump_none_passthrough(self):
        """None passes through unchanged."""
        s = TypeSerializer()
        assert s.dump(None) is None

    def test_dump_string_passthrough(self):
        """Strings pass through unchanged."""
        s = TypeSerializer()
        assert s.dump("hello") == "hello"
        assert s.dump("") == ""

    def test_dump_int_passthrough(self):
        """Integers pass through unchanged."""
        s = TypeSerializer()
        assert s.dump(42) == 42
        assert s.dump(0) == 0
        assert s.dump(-1) == -1

    def test_dump_float_passthrough(self):
        """Floats pass through unchanged."""
        s = TypeSerializer()
        assert s.dump(3.14) == 3.14
        assert s.dump(0.0) == 0.0

    def test_dump_bool_passthrough(self):
        """Booleans pass through unchanged."""
        s = TypeSerializer()
        assert s.dump(True) is True
        assert s.dump(False) is False

    def test_dump_bytes_passthrough(self):
        """Bytes pass through unchanged."""
        s = TypeSerializer()
        assert s.dump(b"hello") == b"hello"

    def test_dump_dict_recursive(self):
        """Dicts are recursively processed."""
        s = TypeSerializer()
        obj = PydanticModel(name="test", value=1)
        result = s.dump({"key": obj, "other": "value"})
        assert result == {"key": {"name": "test", "value": 1}, "other": "value"}

    def test_dump_nested_dict(self):
        """Nested dicts are recursively processed."""
        s = TypeSerializer()
        obj = PydanticModel(name="inner", value=42)
        result = s.dump({"outer": {"nested": obj}})
        assert result == {"outer": {"nested": {"name": "inner", "value": 42}}}

    def test_dump_list_recursive(self):
        """Lists are recursively processed."""
        s = TypeSerializer()
        objs = [PydanticModel(name="a", value=1), PydanticModel(name="b", value=2)]
        result = s.dump(objs)
        assert result == [{"name": "a", "value": 1}, {"name": "b", "value": 2}]

    def test_dump_tuple_recursive(self):
        """Tuples are recursively processed to lists."""
        s = TypeSerializer()
        objs = (PydanticModel(name="a", value=1),)
        result = s.dump(objs)
        assert result == [{"name": "a", "value": 1}]

    def test_dump_pydantic_v2(self):
        """Pydantic v2 models use model_dump()."""
        s = TypeSerializer()
        obj = PydanticModel(name="test", value=42)
        assert s.dump(obj) == {"name": "test", "value": 42}

    def test_dump_nested_pydantic(self):
        """Nested Pydantic models are serialized."""
        s = TypeSerializer()
        inner = PydanticModel(name="inner", value=1)
        outer = NestedPydanticModel(outer="outer", inner=inner)
        result = s.dump(outer)
        assert result == {"outer": "outer", "inner": {"name": "inner", "value": 1}}

    def test_dump_dataclass(self):
        """Dataclasses use asdict()."""
        s = TypeSerializer()
        obj = DataclassModel(name="test", value=42)
        assert s.dump(obj) == {"name": "test", "value": 42}

    def test_dump_nested_dataclass(self):
        """Nested dataclasses are serialized."""
        s = TypeSerializer()
        inner = DataclassModel(name="inner", value=1)
        outer = NestedDataclass(outer="outer", inner=inner)
        result = s.dump(outer)
        assert result == {"outer": "outer", "inner": {"name": "inner", "value": 1}}

    def test_dump_convention_to_dict(self):
        """Classes with to_dict() use that method."""
        s = TypeSerializer()
        obj = ConventionClass(name="test", value=42)
        assert s.dump(obj) == {"name": "test", "value": 42}

    def test_dump_named_tuple(self):
        """Named tuples use _asdict()."""
        s = TypeSerializer()
        obj = PersonTuple(name="Alice", age=30)
        assert s.dump(obj) == {"name": "Alice", "age": 30}

    def test_dump_custom_serializer(self):
        """Custom serializers take precedence."""
        s = TypeSerializer(custom={PydanticModel: {"dump": lambda o: {"custom": o.name}}})
        obj = PydanticModel(name="test", value=42)
        assert s.dump(obj) == {"custom": "test"}

    def test_dump_custom_serializer_for_specific_type(self):
        """Custom serializer only affects specific type."""
        s = TypeSerializer(custom={PydanticModel: {"dump": lambda o: {"custom": o.name}}})
        # Pydantic model uses custom
        pydantic_obj = PydanticModel(name="test", value=42)
        assert s.dump(pydantic_obj) == {"custom": "test"}
        # Dataclass uses default
        dataclass_obj = DataclassModel(name="test", value=42)
        assert s.dump(dataclass_obj) == {"name": "test", "value": 42}

    def test_dump_mixed_collection(self):
        """Mixed collections with different types are handled."""
        s = TypeSerializer()
        data = {
            "pydantic": PydanticModel(name="p", value=1),
            "dataclass": DataclassModel(name="d", value=2),
            "list": [PydanticModel(name="l", value=3)],
            "primitive": "string",
            "number": 42,
        }
        result = s.dump(data)
        assert result == {
            "pydantic": {"name": "p", "value": 1},
            "dataclass": {"name": "d", "value": 2},
            "list": [{"name": "l", "value": 3}],
            "primitive": "string",
            "number": 42,
        }

    def test_dump_unknown_object_passthrough(self):
        """Unknown objects without serialization methods pass through."""
        s = TypeSerializer()

        class UnknownClass:
            def __init__(self):
                self.data = "test"

        obj = UnknownClass()
        # Should return as-is (may fail JSON serialization downstream)
        result = s.dump(obj)
        assert result is obj


class TestLoad:
    """Test deserialization (dict → object)."""

    def test_load_no_type_hint_passthrough(self):
        """No type hint returns data as-is."""
        s = TypeSerializer()
        data = {"name": "test", "value": 42}
        assert s.load(data, None) == data

    def test_load_empty_annotation_passthrough(self):
        """Empty annotation returns data as-is."""
        import inspect

        s = TypeSerializer()
        data = {"name": "test", "value": 42}
        assert s.load(data, inspect.Parameter.empty) == data

    def test_load_non_dict_passthrough(self):
        """Non-dict values pass through regardless of type hint."""
        s = TypeSerializer()
        assert s.load("hello", PydanticModel) == "hello"
        assert s.load(42, PydanticModel) == 42
        assert s.load(["a", "b"], PydanticModel) == ["a", "b"]

    def test_load_non_type_passthrough(self):
        """Generic type hints (List[str], Optional[X]) pass through."""
        from typing import List, Optional

        s = TypeSerializer()
        data = {"name": "test"}
        # These are not `type` instances, so should pass through
        assert s.load(data, List[str]) == data
        assert s.load(data, Optional[str]) == data

    def test_load_primitive_type_passthrough(self):
        """Primitive type hints pass through."""
        s = TypeSerializer()
        assert s.load("hello", str) == "hello"
        assert s.load(42, int) == 42
        # Dict type hint with dict value passes through
        assert s.load({"a": 1}, dict) == {"a": 1}

    def test_load_pydantic_v2(self):
        """Dicts are converted to Pydantic models."""
        s = TypeSerializer()
        data = {"name": "test", "value": 42}
        result = s.load(data, PydanticModel)
        assert isinstance(result, PydanticModel)
        assert result.name == "test"
        assert result.value == 42

    def test_load_nested_pydantic(self):
        """Nested Pydantic models are constructed."""
        s = TypeSerializer()
        data = {"outer": "test", "inner": {"name": "inner", "value": 1}}
        result = s.load(data, NestedPydanticModel)
        assert isinstance(result, NestedPydanticModel)
        assert result.outer == "test"
        assert isinstance(result.inner, PydanticModel)
        assert result.inner.name == "inner"

    def test_load_dataclass(self):
        """Dicts are converted to dataclasses."""
        s = TypeSerializer()
        data = {"name": "test", "value": 42}
        result = s.load(data, DataclassModel)
        assert isinstance(result, DataclassModel)
        assert result.name == "test"
        assert result.value == 42

    def test_load_convention_from_dict(self):
        """Classes with from_dict() use that method."""
        s = TypeSerializer()
        data = {"name": "test", "value": 42}
        result = s.load(data, ConventionClass)
        assert isinstance(result, ConventionClass)
        assert result.name == "test"
        assert result.value == 42

    def test_load_custom_deserializer(self):
        """Custom deserializers take precedence."""
        s = TypeSerializer(
            custom={PydanticModel: {"load": lambda d: PydanticModel(name=d["custom"], value=0)}}
        )
        data = {"custom": "test"}
        result = s.load(data, PydanticModel)
        assert result.name == "test"
        assert result.value == 0

    def test_load_generic_constructor_fallback(self):
        """Falls back to Type(**data) for unknown classes."""
        s = TypeSerializer()
        data = {"name": "test", "value": 42}
        result = s.load(data, SimpleClass)
        assert isinstance(result, SimpleClass)
        assert result.name == "test"
        assert result.value == 42

    def test_load_invalid_data_returns_dict(self):
        """Invalid data for target type returns dict as fallback."""
        s = TypeSerializer()
        # Missing required field - Pydantic will fail
        data = {"name": "test"}  # missing 'value'
        result = s.load(data, PydanticModel)
        # Should return dict as-is when construction fails
        assert result == data

    def test_load_extra_fields_handled(self):
        """Extra fields in data are handled by Pydantic."""
        s = TypeSerializer()
        data = {"name": "test", "value": 42, "extra": "ignored"}
        result = s.load(data, PydanticModel)
        # Pydantic by default ignores extra fields
        assert isinstance(result, PydanticModel)
        assert result.name == "test"
        assert result.value == 42


class TestRoundTrip:
    """Test dump → load round trips."""

    def test_pydantic_roundtrip(self):
        """Pydantic objects survive dump/load cycle."""
        s = TypeSerializer()
        original = PydanticModel(name="test", value=42)
        dumped = s.dump(original)
        loaded = s.load(dumped, PydanticModel)
        assert loaded == original

    def test_nested_pydantic_roundtrip(self):
        """Nested Pydantic objects survive dump/load cycle."""
        s = TypeSerializer()
        inner = PydanticModel(name="inner", value=1)
        original = NestedPydanticModel(outer="outer", inner=inner)
        dumped = s.dump(original)
        loaded = s.load(dumped, NestedPydanticModel)
        assert loaded == original

    def test_dataclass_roundtrip(self):
        """Dataclass objects survive dump/load cycle."""
        s = TypeSerializer()
        original = DataclassModel(name="test", value=42)
        dumped = s.dump(original)
        loaded = s.load(dumped, DataclassModel)
        assert loaded == original

    def test_convention_class_roundtrip(self):
        """Convention class objects survive dump/load cycle."""
        s = TypeSerializer()
        original = ConventionClass(name="test", value=42)
        dumped = s.dump(original)
        loaded = s.load(dumped, ConventionClass)
        assert loaded.name == original.name
        assert loaded.value == original.value


class TestCustomSerializers:
    """Test custom serializer functionality."""

    def test_custom_dump_only(self):
        """Custom serializer with dump only."""
        s = TypeSerializer(custom={PydanticModel: {"dump": lambda o: {"only_name": o.name}}})
        obj = PydanticModel(name="test", value=42)
        assert s.dump(obj) == {"only_name": "test"}
        # Load should still use default
        data = {"name": "test", "value": 42}
        result = s.load(data, PydanticModel)
        assert isinstance(result, PydanticModel)

    def test_custom_load_only(self):
        """Custom serializer with load only."""
        s = TypeSerializer(
            custom={PydanticModel: {"load": lambda d: PydanticModel(name=d.get("n", ""), value=0)}}
        )
        # Dump should use default
        obj = PydanticModel(name="test", value=42)
        assert s.dump(obj) == {"name": "test", "value": 42}
        # Load uses custom
        data = {"n": "custom"}
        result = s.load(data, PydanticModel)
        assert result.name == "custom"
        assert result.value == 0

    def test_multiple_custom_serializers(self):
        """Multiple custom serializers for different types."""
        s = TypeSerializer(
            custom={
                PydanticModel: {"dump": lambda o: {"p": o.name}},
                DataclassModel: {"dump": lambda o: {"d": o.name}},
            }
        )
        pydantic = PydanticModel(name="pydantic", value=1)
        dataclass = DataclassModel(name="dataclass", value=2)

        assert s.dump(pydantic) == {"p": "pydantic"}
        assert s.dump(dataclass) == {"d": "dataclass"}

    def test_custom_serializer_error_falls_back(self):
        """Custom serializer errors fall back to auto-detection."""
        # Custom dump that raises an error
        def bad_dump(obj):
            raise ValueError("Custom dump failed")

        s = TypeSerializer(custom={PydanticModel: {"dump": bad_dump}})
        obj = PydanticModel(name="test", value=42)
        # Should fall back to model_dump()
        result = s.dump(obj)
        assert result == {"name": "test", "value": 42}


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_dict(self):
        """Empty dict passes through on dump and load."""
        s = TypeSerializer()
        assert s.dump({}) == {}
        assert s.load({}, None) == {}

    def test_empty_list(self):
        """Empty list passes through."""
        s = TypeSerializer()
        assert s.dump([]) == []

    def test_deeply_nested_structure(self):
        """Deeply nested structures are handled."""
        s = TypeSerializer()
        obj = PydanticModel(name="deep", value=1)
        deep = {"a": {"b": {"c": {"d": [obj]}}}}
        result = s.dump(deep)
        assert result == {"a": {"b": {"c": {"d": [{"name": "deep", "value": 1}]}}}}

    def test_list_of_mixed_types(self):
        """Lists with mixed types are handled."""
        s = TypeSerializer()
        mixed = [
            PydanticModel(name="p", value=1),
            DataclassModel(name="d", value=2),
            "string",
            42,
            None,
        ]
        result = s.dump(mixed)
        assert result == [
            {"name": "p", "value": 1},
            {"name": "d", "value": 2},
            "string",
            42,
            None,
        ]

    def test_serializer_instance_isolation(self):
        """Different serializer instances are isolated."""
        s1 = TypeSerializer(custom={PydanticModel: {"dump": lambda o: {"s1": o.name}}})
        s2 = TypeSerializer(custom={PydanticModel: {"dump": lambda o: {"s2": o.name}}})

        obj = PydanticModel(name="test", value=42)
        assert s1.dump(obj) == {"s1": "test"}
        assert s2.dump(obj) == {"s2": "test"}

    def test_none_in_collection(self):
        """None values in collections are preserved."""
        s = TypeSerializer()
        data = {"key": None, "list": [None, PydanticModel(name="a", value=1), None]}
        result = s.dump(data)
        assert result == {"key": None, "list": [None, {"name": "a", "value": 1}, None]}
