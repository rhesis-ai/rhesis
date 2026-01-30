"""Unified type serialization for input/output handling.

This module provides bidirectional serialization (dump/load) with automatic
detection of common patterns (Pydantic, dataclasses, etc.) and support for
custom serializers.
"""

import dataclasses
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Declarative strategies: (predicate, action)
# Order matters - first match wins

DUMP_STRATEGIES: list[tuple[Callable[[Any], bool], Callable[[Any], Any]]] = [
    # Pydantic v2 models
    (lambda o: hasattr(o, "model_dump"), lambda o: o.model_dump()),
    # Pydantic v1 models
    (lambda o: hasattr(o, "__fields__") and hasattr(o, "dict"), lambda o: o.dict()),
    # Dataclasses (exclude the type itself, only instances)
    (
        lambda o: dataclasses.is_dataclass(o) and not isinstance(o, type),
        dataclasses.asdict,
    ),
    # Convention: to_dict() method
    (
        lambda o: hasattr(o, "to_dict") and callable(getattr(o, "to_dict", None)),
        lambda o: o.to_dict(),
    ),
    # NamedTuple
    (lambda o: hasattr(o, "_asdict"), lambda o: o._asdict()),
]

LOAD_STRATEGIES: list[tuple[Callable[[type], bool], Callable[[type, dict], Any]]] = [
    # Pydantic v2 models
    (lambda t: hasattr(t, "model_validate"), lambda t, d: t.model_validate(d)),
    # Pydantic v1 models
    (lambda t: hasattr(t, "parse_obj"), lambda t, d: t.parse_obj(d)),
    # Dataclasses
    (lambda t: dataclasses.is_dataclass(t), lambda t, d: t(**d)),
    # Convention: from_dict() class method
    (
        lambda t: hasattr(t, "from_dict") and callable(getattr(t, "from_dict", None)),
        lambda t, d: t.from_dict(d),
    ),
]


class TypeSerializer:
    """Unified bidirectional serialization with auto-detection and custom overrides.

    All values flow through the same path - the serializer decides what to do
    based on the value type and target type hints.

    Example:
        >>> serializer = TypeSerializer()
        >>> # Dump: object → dict
        >>> serializer.dump(pydantic_model)  # Returns dict
        >>> # Load: dict → object
        >>> serializer.load(data_dict, PydanticModel)  # Returns PydanticModel instance

        >>> # With custom serializers
        >>> serializer = TypeSerializer(custom={
        ...     MyClass: {
        ...         "dump": lambda obj: obj.to_custom_format(),
        ...         "load": lambda d: MyClass.from_custom(d),
        ...     }
        ... })
    """

    # Types that pass through without conversion
    PASSTHROUGH_TYPES = (dict, list, set, tuple, str, int, float, bool, bytes, type(None))

    def __init__(self, custom: dict | None = None):
        """Initialize the serializer.

        Args:
            custom: Custom serializers for specific types.
                Format: {Type: {"dump": callable, "load": callable}}
        """
        self.custom = custom or {}

    def dump(self, obj: Any) -> Any:
        """Serialize object to JSON-compatible format (dict/list/primitive).

        Handles:
        - Primitives: pass through unchanged
        - Collections (dict, list, tuple): recursively process
        - Pydantic models: model_dump() or dict()
        - Dataclasses: asdict()
        - Objects with to_dict(): call that method
        - Custom serializers: use registered dump function

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable representation
        """
        # Primitives pass through
        if obj is None or isinstance(obj, (str, int, float, bool, bytes)):
            return obj

        # Recursively handle dicts
        if isinstance(obj, dict):
            return {k: self.dump(v) for k, v in obj.items()}

        # Custom serializer takes precedence over auto-detection
        obj_type = type(obj)
        if obj_type in self.custom and "dump" in self.custom[obj_type]:
            try:
                return self.custom[obj_type]["dump"](obj)
            except Exception as e:
                logger.warning(f"Custom dump serializer failed for {obj_type}: {e}")
                # Fall through to auto-detection

        # Auto-detect using strategies (before handling generic lists/tuples)
        # This ensures NamedTuples use _asdict() instead of being treated as tuples
        for pred, action in DUMP_STRATEGIES:
            if pred(obj):
                try:
                    return action(obj)
                except Exception as e:
                    logger.debug(f"Dump strategy failed for {obj_type}: {e}")
                    continue

        # Recursively handle lists and tuples (after checking for NamedTuple)
        if isinstance(obj, (list, tuple)):
            return [self.dump(item) for item in obj]

        # Fallback: return as-is (may fail JSON serialization downstream)
        logger.debug(f"No dump strategy matched for {obj_type}, returning as-is")
        return obj

    def load(self, data: Any, target_type: type | None = None) -> Any:
        """Deserialize data to target type if applicable.

        Handles:
        - No type hint or special types: pass through
        - Non-dict values: pass through (nothing to construct from)
        - Primitive/collection type hints: pass through
        - Pydantic models: model_validate() or parse_obj()
        - Dataclasses: Type(**data)
        - Objects with from_dict(): call that method
        - Custom serializers: use registered load function
        - Generic fallback: try Type(**data)

        Args:
            data: Data to deserialize (typically a dict)
            target_type: Expected type (from function parameter annotation)

        Returns:
            Constructed object or original data if conversion not applicable
        """
        # No conversion needed cases
        if target_type is None:
            return data

        if target_type == inspect.Parameter.empty:
            return data

        if not isinstance(data, dict):
            return data

        if not isinstance(target_type, type):
            # Generic types like List[str], Optional[X], etc. are not `type` instances
            return data

        if target_type in self.PASSTHROUGH_TYPES:
            return data

        # Custom deserializer takes precedence
        if target_type in self.custom and "load" in self.custom[target_type]:
            try:
                return self.custom[target_type]["load"](data)
            except Exception as e:
                logger.warning(f"Custom load serializer failed for {target_type}: {e}")
                # Fall through to auto-detection

        # Auto-detect using strategies (with error handling)
        for pred, action in LOAD_STRATEGIES:
            if pred(target_type):
                try:
                    return action(target_type, data)
                except (TypeError, ValueError) as e:
                    logger.debug(f"Load strategy failed for {target_type}: {e}")
                    continue

        # Generic fallback: try constructor
        try:
            return target_type(**data)
        except (TypeError, ValueError) as e:
            logger.debug(f"Generic constructor failed for {target_type}: {e}")
            return data  # Ultimate fallback: return dict as-is
