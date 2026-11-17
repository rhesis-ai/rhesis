"""What publish freezes about the endpoint, and the hashes that prove a report unchanged."""

import hashlib
import json
from typing import Any, Dict, Iterable, List

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.report.counting import CountedResult

# Never auth, tokens, secrets or request headers: the snapshot ends up in a PDF.
_ENDPOINT_FIELDS = (
    "id",
    "name",
    "description",
    "environment",
    "connection_type",
    "url",
    "method",
    "endpoint_path",
    "version_info",
    "endpoint_metadata",
    "request_mapping",
    "response_mapping",
)


def endpoint_snapshot(endpoint: Endpoint) -> Dict[str, Any]:
    return {field: _jsonable(getattr(endpoint, field, None)) for field in _ENDPOINT_FIELDS}


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _result_row(result: CountedResult) -> List[Any]:
    return [
        str(result.test_result_id),
        str(result.test_id),
        str(result.test_run_id),
        str(result.requirement_id) if result.requirement_id else None,
        result.execution,
        result.verdict,
        result.overridden,
    ]


def run_hashes(counted: Iterable[CountedResult]) -> Dict[str, str]:
    """One hash per run over the results it contributed."""
    by_run: Dict[str, List[List[Any]]] = {}
    for result in counted:
        by_run.setdefault(str(result.test_run_id), []).append(_result_row(result))
    return {run_id: _digest(sorted(rows, key=str)) for run_id, rows in by_run.items()}


def snapshot_hash(frozen: Dict[str, Any], counted: Iterable[CountedResult]) -> str:
    """Hash over everything a published report shows, so a PDF can be checked against it."""
    return _digest({**frozen, "results": sorted((_result_row(r) for r in counted), key=str)})
