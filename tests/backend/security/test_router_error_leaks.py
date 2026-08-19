"""Guard against handlers returning internal error text to clients.

A broad ``except Exception as e`` that puts ``e`` into ``detail=`` hands the
caller whatever the failure happened to say -- SQLAlchemy statements, OAuth
provider internals, filesystem paths. Narrow handlers (``except ValueError``)
are fine and deliberate: those messages are written for the user to read.

The scan covers ``app/routers``, ``app/utils`` and ``app/services`` because a
leak built in a helper reaches the client exactly like one written in the
router -- ``handle_execution_error`` and the connection-test result bodies both
live outside ``routers/``.

What is deliberately *not* a leak: a 4xx detail (the handler passes those
through on purpose, so a guard that flagged them would argue with the contract
it protects) and an ``UpstreamHTTPException`` (the opt-in that says "this text
is the caller's own system's").

``KNOWN_LEAKS`` is the backlog being worked off in batches. A file's count may
only ever go down. When it hits zero, delete the entry.
"""

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import pytest

APP_DIR = (
    Path(__file__).resolve().parents[3] / "apps" / "backend" / "src" / "rhesis" / "backend" / "app"
)

#: Subtrees of ``app/`` whose error text can reach a client.
SCAN_DIRS = ("routers", "utils", "services")

#: Not scanned. Endpoint invocation exists to report what went wrong with the
#: *caller's own* endpoint -- a refused connection, an unparseable body -- which
#: is the same reasoning that exempts UpstreamHTTPException from masking. Every
#: error string these build is that report, so scanning them is all wolf-crying.
EXEMPT_DIRS = ("services/invokers",)

#: Exception types broad enough that their text is of unknown origin. The DB and
#: HTTP families are here because their messages carry SQL statements,
#: connection strings and URLs with credentials in them.
BROAD_EXCEPTIONS = {
    "Exception",
    "BaseException",
    # SQLAlchemy
    "SQLAlchemyError",
    "DBAPIError",
    "DatabaseError",
    "OperationalError",
    "IntegrityError",
    "ProgrammingError",
    "DataError",
    "InvalidRequestError",
    "InterfaceError",
    # httpx / requests
    "HTTPError",
    "TransportError",
    "RequestError",
    "HTTPStatusError",
    "ConnectError",
    "RequestException",
    "ConnectionError",
    # stdlib failures that carry paths and command lines
    "OSError",
    "IOError",
    "CalledProcessError",
    "SubprocessError",
}

#: Keyword arguments that are response text wherever they appear.
RESPONSE_FIELDS = {"detail", "content", "headers"}

#: Fields that only mean "shown to the caller" on something response-shaped.
#: ``update_test_run_status(..., error=str(exc))`` writes a DB column; the same
#: keyword on a ``*Result`` or ``*Response`` is a body being built.
RESULT_FIELDS = {"detail", "message", "msg", "error", "error_message", "reason"}

#: Keys of a dict literal that is returned or handed to ``content=``.
BODY_KEYS = RESULT_FIELDS | {"content", "details", "errors"}

#: Calls whose *positional* arguments are response text. ``HTTPException(500,
#: f"boom: {e}")`` is the same leak as ``detail=f"boom: {e}"``.
RESPONSE_CALLS = {
    "HTTPException",
    "PublicHTTPException",
    "StarletteHTTPException",
    "JSONResponse",
    "PlainTextResponse",
    "HTMLResponse",
    "Response",
}

#: HTTPException classes whose first positional argument is the status code.
HTTP_EXCEPTION_CALLS = {
    "HTTPException",
    "PublicHTTPException",
    "StarletteHTTPException",
    "FastAPIHTTPException",
}

#: The one blessed relay. UpstreamHTTPException *means* "this text is the
#: caller's own system's, pass it through" -- an opt-in a reviewer can grep for,
#: and the reason endpoint testing can say "connection refused" at all.
#: PublicHTTPException is not exempt: its detail must be a literal.
UPSTREAM_RELAY = {"UpstreamHTTPException"}

#: Reachable without ``as e``: ``except Exception:`` plus ``traceback.format_exc()``
#: leaks the whole stack, and the handler has no exception name to track.
TAINTED_MODULES = {"traceback"}

#: relative path under app/ -> number of leaks still tolerated. Only ever shrinks.
#: Every entry is a real leak found when the scan grew past ``routers/*.py``, not
#: a false positive to live with. The owner note says who is clearing it.
KNOWN_LEAKS: dict[str, int] = {
    # unowned: connector replies carrying str(e) over the websocket.
    "services/connector/handlers/registration.py": 3,
    "services/connector/rpc_client.py": 3,
    # unowned: AutoConfigureResult(error=f"Could not parse the input: {e}").
    "services/endpoint/auto_configure.py": 1,
    # unowned: {"success": False, "error": str(validation_error)}.
    "services/endpoint/validation.py": 1,
    # model-connection agent: ModelConnectionTestResult(message=f"...{e}").
    "services/model_connection.py": 2,
    # unowned: association helpers answer 200 with f"...: {str(e)}" in `message`.
    "services/test.py": 3,
    "services/test_set.py": 1,
    # mcp agent: handle_mcp_exception picks its class at runtime, so the guard
    # cannot tell the blessed UpstreamHTTPException relay from the masked
    # HTTPException that gets detail=str(e) for a non-application MCPError.
    "services/tool/mcp/exceptions.py": 1,
}


@dataclass
class Taint:
    """Names and attributes known to hold exception text."""

    names: set[str] = field(default_factory=set)
    attrs: set[str] = field(default_factory=set)

    def __bool__(self) -> bool:
        return bool(self.names or self.attrs)

    def __eq__(self, other: "Taint") -> bool:
        return self.names == other.names and self.attrs == other.attrs

    def copy(self) -> "Taint":
        return Taint(set(self.names), set(self.attrs))


def _exception_names(node: ast.AST) -> list[str]:
    """The bare names in an exception type expression, ``a.b.C`` included."""
    if isinstance(node, ast.Tuple):
        return [n for elt in node.elts for n in _exception_names(elt)]
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):  # builtins.Exception, sqlalchemy.exc.DBAPIError
        return [node.attr]
    return []


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:  # bare `except:`
        return True
    return any(name in BROAD_EXCEPTIONS for name in _exception_names(handler.type))


def _references(node: ast.AST, taint: Taint) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in taint.names:
            return True
        if isinstance(n, ast.Attribute) and n.attr in taint.attrs:
            return True
    return False


def _add_target(target: ast.AST, taint: Taint) -> None:
    """Record whatever ``target`` writes to, however it is spelled."""
    if isinstance(target, ast.Name):
        taint.names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _add_target(elt, taint)
    elif isinstance(target, ast.Starred):
        _add_target(target.value, taint)
    elif isinstance(target, ast.Attribute):
        taint.attrs.add(target.attr)
    elif isinstance(target, ast.Subscript):
        # `d["msg"] = str(e)` taints the container: which key it went into is
        # more than this scan can follow.
        _add_target(target.value, taint)


def _grow(scope: ast.AST, taint: Taint) -> Taint:
    """Every local the exception text was copied into.

    ``error_msg = str(e)`` then ``detail=f"...{error_msg}"`` is the same leak
    written in two steps, and checking only the exception name misses it.
    Iterates to a fixpoint so chains of copies are caught too.
    """
    while True:
        grown = taint.copy()
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign) and _references(node.value, taint):
                for target in node.targets:
                    _add_target(target, grown)
            elif isinstance(node, ast.AugAssign) and _references(node.value, taint):
                _add_target(node.target, grown)
            elif (
                isinstance(node, ast.AnnAssign)
                and node.value is not None
                and _references(node.value, taint)
            ):
                _add_target(node.target, grown)
            elif isinstance(node, ast.NamedExpr) and _references(node.value, taint):
                _add_target(node.target, grown)
        if grown == taint:
            return taint
        taint = grown


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_response_shaped(name: str) -> bool:
    """A call that builds something the caller reads, by name alone."""
    lowered = name.lower()
    return name in RESPONSE_CALLS or "response" in lowered or "result" in lowered


def _dict_leaks(node: ast.AST, taint: Taint) -> bool:
    """A dict literal whose body carries exception text out to the caller."""
    if not isinstance(node, ast.Dict):
        return False
    return any(
        isinstance(key, ast.Constant) and key.value in BODY_KEYS and _references(value, taint)
        for key, value in zip(node.keys, node.values)
    )


def _response_status(node: ast.Call, name: str) -> int | None:
    """The literal status this call answers with, or None if it isn't literal."""
    for kw in node.keywords:
        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
            return kw.value.value if isinstance(kw.value.value, int) else None
    if name in HTTP_EXCEPTION_CALLS and node.args and isinstance(node.args[0], ast.Constant):
        first = node.args[0].value
        return first if isinstance(first, int) else None
    return None


def _is_deliberate_client_error(node: ast.Call, name: str) -> bool:
    """A 4xx detail is the one message the stack deliberately passes through.

    ``http_exception_handler`` masks 5xx and leaves anything under 500 alone
    because a 400 is written for the caller to read -- an unparseable OData
    filter, a provider answering "unknown model". Flagging those would make the
    guard argue with the contract it exists to protect. An unknown or computed
    status is treated as maskable: it may well be a 500.
    """
    status = _response_status(node, name)
    return status is not None and 400 <= status < 500


def _leaks_in(scope: ast.AST, taint: Taint) -> set[int]:
    leaks: set[int] = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in UPSTREAM_RELAY or _is_deliberate_client_error(node, name):
                continue
            fields = RESPONSE_FIELDS | (RESULT_FIELDS if _is_response_shaped(name) else set())
            if name in RESPONSE_CALLS and any(_references(arg, taint) for arg in node.args):
                leaks.add(node.lineno)
            for kw in node.keywords:
                if kw.arg in fields and _references(kw.value, taint):
                    leaks.add(node.lineno)
                # `HTTPException(**{"detail": str(e)})`
                elif kw.arg is None and _dict_leaks(kw.value, taint):
                    leaks.add(node.lineno)
        # `exc = HTTPException(...)` then `exc.detail = str(e)`
        elif isinstance(node, ast.Assign) and _references(node.value, taint):
            if any(
                isinstance(t, ast.Attribute) and t.attr in RESPONSE_FIELDS for t in node.targets
            ):
                leaks.add(node.lineno)
        # A 200 whose body says what went wrong: `return {"error": str(e)}`
        elif isinstance(node, ast.Return) and node.value is not None:
            if _dict_leaks(node.value, taint):
                leaks.add(node.lineno)
    return leaks


def _exception_parameters(fn: ast.AST) -> Taint:
    """Parameters annotated as a broad exception type.

    ``def handle_execution_error(error: Exception)`` builds its detail from an
    exception it never caught, so an except-handler-only scan cannot see it.
    """
    taint = Taint()
    args = fn.args
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        if arg.annotation is not None and any(
            name in BROAD_EXCEPTIONS for name in _exception_names(arg.annotation)
        ):
            taint.names.add(arg.arg)
    return taint


def find_leaks(source: str) -> list[int]:
    """Line numbers where internal exception text is handed to the client."""
    leaks: set[int] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if not _is_broad(node):
                continue
            taint = Taint(set(TAINTED_MODULES), set())
            if node.name:
                taint.names.add(node.name)
            leaks |= _leaks_in(node, _grow(node, taint))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            taint = _exception_parameters(node)
            if taint:
                leaks |= _leaks_in(node, _grow(node, taint))
    return sorted(leaks)


def _key(path: Path) -> str:
    return path.relative_to(APP_DIR).as_posix()


def scanned_files() -> list[Path]:
    return sorted(
        p
        for directory in SCAN_DIRS
        for p in (APP_DIR / directory).rglob("*.py")
        if p.name != "__init__.py" and not _key(p).startswith(EXEMPT_DIRS)
    )


@pytest.mark.parametrize("path", scanned_files(), ids=_key)
def test_handler_does_not_leak_internal_errors(path: Path):
    leaks = find_leaks(path.read_text())
    key = _key(path)
    allowed = KNOWN_LEAKS.get(key, 0)

    assert len(leaks) <= allowed, (
        f"{key} leaks internal exception text to clients at lines {leaks}. "
        f"Log the exception and return a generic message instead -- see "
        f"rhesis.backend.app.error_handlers.internal_error."
    )

    if len(leaks) < allowed:
        pytest.fail(
            f"{key} now has {len(leaks)} leaks, fewer than the allowed {allowed}. "
            f"Lower KNOWN_LEAKS['{key}'] to {len(leaks)} "
            f"({'or delete the entry' if len(leaks) == 0 else 'to lock the improvement in'})."
        )


def test_allowlist_has_no_stale_entries():
    """A file listed in KNOWN_LEAKS must still exist and still be scanned."""
    keys = {_key(p) for p in scanned_files()}
    assert not (set(KNOWN_LEAKS) - keys), (
        f"KNOWN_LEAKS names files that are no longer scanned: {set(KNOWN_LEAKS) - keys}"
    )


def test_scan_covers_the_helpers_that_build_error_responses():
    """The scan is recursive and reaches past routers/, or it guards nothing."""
    keys = {_key(p) for p in scanned_files()}

    assert "utils/execution_validation.py" in keys
    assert "services/model_connection.py" in keys
    assert any("/" in key.split("/", 1)[1] for key in keys), (
        "no file found in a subpackage -- the glob is not recursive"
    )


# --- the guard's own behaviour, pinned against inline snippets ---------------
#
# Each case is a leak variant that once slipped through. Testing against strings
# rather than the real tree keeps these true no matter what the routers contain.

LEAKING = {
    "positional_detail": """
        try:
            pass
        except Exception as e:
            raise HTTPException(500, f"boom: {e}")
    """,
    "database_error_is_broad": """
        try:
            pass
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=str(e))
    """,
    "operational_error_is_broad": """
        try:
            pass
        except OperationalError as e:
            raise HTTPException(status_code=500, detail=str(e))
    """,
    "http_client_error_is_broad": """
        try:
            pass
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=str(e))
    """,
    "subprocess_error_is_broad": """
        try:
            pass
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=str(e))
    """,
    "dotted_broad_exception": """
        try:
            pass
        except builtins.Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    """,
    "aug_assign": """
        try:
            pass
        except Exception as e:
            msg = "Failed: "
            msg += str(e)
            raise HTTPException(status_code=500, detail=msg)
    """,
    "tuple_unpack": """
        try:
            pass
        except Exception as e:
            msg, code = str(e), 500
            raise HTTPException(status_code=code, detail=msg)
    """,
    "dict_item_target": """
        try:
            pass
        except Exception as e:
            payload = {}
            payload["msg"] = str(e)
            raise HTTPException(status_code=500, detail=payload["msg"])
    """,
    "attribute_target": """
        try:
            pass
        except Exception as e:
            self.msg = str(e)
            raise HTTPException(status_code=500, detail=self.msg)
    """,
    "detail_assigned_after_construction": """
        try:
            pass
        except Exception as e:
            exc = HTTPException(status_code=500, detail="An unexpected error occurred.")
            exc.detail = str(e)
            raise exc
    """,
    "traceback_without_as": """
        try:
            pass
        except Exception:
            raise HTTPException(status_code=500, detail=traceback.format_exc())
    """,
    "kwargs_splat": """
        try:
            pass
        except Exception as e:
            raise HTTPException(**{"detail": str(e)})
    """,
    "json_response_content": """
        try:
            pass
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})
    """,
    "ok_body_carrying_the_error": """
        try:
            pass
        except Exception as e:
            return {"success": False, "error": str(e)}
    """,
    "result_object_message": """
        try:
            pass
        except Exception as e:
            return ModelConnectionTestResult(success=False, message=f"Unexpected error: {e}")
    """,
    "header_channel": """
        try:
            pass
        except Exception as e:
            raise HTTPException(
                500, detail="Nothing to see.", headers={"X-Err": str(e)}
            )
    """,
    "public_exception_detail_must_be_a_literal": """
        try:
            pass
        except Exception as e:
            raise PublicHTTPException(status_code=503, detail=f"Garak failed: {e}")
    """,
    "exception_parameter_outside_any_handler": """
        def handle_execution_error(error: Exception) -> HTTPException:
            return HTTPException(status_code=500, detail=f"Failed: {error}")
    """,
    "computed_status_could_be_a_500": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=status, detail=str(e))
    """,
    "walrus": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail=(msg := str(e)))
    """,
    "format_call": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail="boom {}".format(e))
    """,
    "percent_interpolation": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail="boom %s" % e)
    """,
    "concatenation": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail="boom " + str(e))
    """,
    "repr_of_exception": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail=repr(e))
    """,
    "exception_args": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail=e.args[0])
    """,
    "copied_then_interpolated": """
        try:
            pass
        except Exception as e:
            error_msg = str(e)
            wrapped = f"Failed: {error_msg}"
            raise HTTPException(status_code=500, detail=wrapped)
    """,
}

CLEAN = {
    "narrow_exception_message_is_deliberate": """
        try:
            pass
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    """,
    "logging_the_exception_is_the_point": """
        try:
            pass
        except Exception as e:
            logger.error("Failed to sync: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="An unexpected error occurred.")
    """,
    "deliberate_client_error_detail": """
        try:
            pass
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing filter: {e}") from e
    """,
    "internal_error_helper": """
        try:
            pass
        except Exception as e:
            raise internal_error(e, context="syncing the test set") from e
    """,
    "public_literal_detail": """
        try:
            pass
        except Exception as e:
            logger.exception("garak missing: %s", e)
            raise PublicHTTPException(status_code=503, detail="Garak package is not installed")
    """,
    "upstream_relay_is_the_blessed_exemption": """
        try:
            pass
        except httpx.HTTPError as e:
            logger.warning("could not reach the provider: %s", e)
            raise UpstreamHTTPException(status_code=502, detail=f"Could not reach it: {e}") from e
    """,
    "re_raising_untouched": """
        try:
            pass
        except Exception as e:
            logger.warning("retrying: %s", e)
            raise
    """,
    "narrow_parameter_annotation": """
        def convert(error: ModelConfigurationError) -> HTTPException:
            return HTTPException(status_code=400, detail=str(error))
    """,
}


def _snippet(source: str) -> str:
    return textwrap.dedent(source).strip("\n")


@pytest.mark.parametrize("name", sorted(LEAKING))
def test_find_leaks_catches(name):
    assert find_leaks(_snippet(LEAKING[name])), f"{name} slipped through the guard"


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_find_leaks_does_not_cry_wolf(name):
    """False positives get the guard deleted, so pin the safe patterns too."""
    assert find_leaks(_snippet(CLEAN[name])) == [], f"{name} was flagged but is safe"
