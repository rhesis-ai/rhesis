"""Sandboxed Jinja2 environment for tenant-written endpoint templates."""

from typing import Any, Tuple

from jinja2.sandbox import ImmutableSandboxedEnvironment, SecurityError

from rhesis.backend.app.services.invokers.templating.filters import TemplateInputError


class UnsafeTemplateError(SecurityError, TemplateInputError):
    """A template tried to reach an attribute the sandbox does not allow."""


class TemplateSandbox(ImmutableSandboxedEnvironment):
    """Raises on unsafe attribute access instead of rendering it as an empty string."""

    def unsafe_undefined(self, obj: Any, attribute: str) -> Any:
        raise UnsafeTemplateError(
            f"access to attribute {attribute!r} of {type(obj).__name__!r} object is not allowed"
        )


def resolve_dotted_path(env: TemplateSandbox, root: Any, path: str) -> Tuple[bool, Any]:
    """Resolve ``a.b.c`` by dict key, then by attribute, with the sandbox's attribute rules."""
    value = root
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif hasattr(value, part):
            attr = getattr(value, part)
            if not env.is_safe_attribute(value, part, attr):
                env.unsafe_undefined(value, part)
            value = attr
        else:
            return False, None
    return True, value
