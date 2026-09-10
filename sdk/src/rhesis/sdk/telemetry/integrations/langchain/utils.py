"""Utility functions and module-level state for LangChain integration."""

from typing import Any, Callable, Optional

# Module-level state for tool patching (singleton pattern)
_original_tool_invoke: Callable | None = None
_original_tool_ainvoke: Callable | None = None
_tool_patching_done: bool = False


class ToolPatchState:
    """Accessor for tool patching state."""

    @staticmethod
    def get_invoke() -> Callable | None:
        return _original_tool_invoke

    @staticmethod
    def set_invoke(func: Callable) -> None:
        global _original_tool_invoke
        _original_tool_invoke = func

    @staticmethod
    def get_ainvoke() -> Callable | None:
        return _original_tool_ainvoke

    @staticmethod
    def set_ainvoke(func: Callable) -> None:
        global _original_tool_ainvoke
        _original_tool_ainvoke = func

    @staticmethod
    def is_done() -> bool:
        return _tool_patching_done

    @staticmethod
    def set_done(done: bool = True) -> None:
        global _tool_patching_done
        _tool_patching_done = done

    @staticmethod
    def reset() -> None:
        """Forget the captured originals.

        Only safe once the class has been restored: the patched methods look
        the original up here on every call.
        """
        global _original_tool_invoke, _original_tool_ainvoke, _tool_patching_done
        _original_tool_invoke = None
        _original_tool_ainvoke = None
        _tool_patching_done = False


def restore_class_method(cls: type, name: str, original: Callable) -> None:
    """Undo an in-place method patch, leaving `cls` as it was found.

    Patching assigns onto the class, which installs an entry in its ``__dict__``
    whether or not the method lived there before. Restoring by assignment alone
    would leave an inherited method shadowed by a copy of itself, so drop the
    override first and only reinstate the original if the class really did
    define it.
    """
    if cls.__dict__.get(name) is not original and name in cls.__dict__:
        delattr(cls, name)
    if getattr(cls, name, None) is not original:
        setattr(cls, name, original)


def ensure_callback_in_config(config: Optional[dict], callback: Any) -> dict:
    """Ensure our callback is included in the RunnableConfig."""
    if config is None:
        config = {}

    callbacks = config.get("callbacks", [])

    # Normalize callback list
    if callbacks is None:
        callbacks = []
    elif hasattr(callbacks, "handlers"):
        callbacks = list(callbacks.handlers)
    elif not isinstance(callbacks, list):
        callbacks = [callbacks]
    else:
        callbacks = list(callbacks)

    # Add our callback if not present
    if not any(isinstance(cb, type(callback)) for cb in callbacks):
        callbacks.append(callback)

    config["callbacks"] = callbacks
    return config
