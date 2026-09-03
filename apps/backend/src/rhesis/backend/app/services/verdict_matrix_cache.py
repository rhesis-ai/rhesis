"""Cache for the encoded verdict grid, once a test run is terminal.

``get_verdict_matrix`` (services/test_run.py) expands the run's whole
``v_metric_stats`` view out of JSONB and rebuilds the grid in an O(rows x tests)
Python loop on every call. For a terminal run (Completed/Partial/Failed/Cancelled)
that result is fixed, so repeating it on every page load -- and, while anyone has
the Summary tab open, every WebSocket-triggered refetch -- buys nothing.

The three review endpoints in routers/test_result.py call ``invalidate``; they are
the only writes that can change a finished run's grid, via the ``has_override`` /
``effective_success`` columns ``services/review_override.py`` maintains. (Trace
reviews write to ``Trace``, which the grid never reads, and a rescore produces a
new run rather than mutating this one.) The TTL is a safety net for a write path
added later without an ``invalidate`` call, not the primary mechanism.

A live run is never cached: its grid changes every few seconds, so any TTL short
enough to be correct is too short to help.
"""

import logging
from typing import Optional

from pydantic import ValidationError

from rhesis.backend.app.schemas.test_run_verdicts import VerdictMatrix
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_PREFIX = "vm:"
# Bounds staleness from a write path not yet wired to invalidate() -- see module
# docstring. Long enough that a run getting steady traffic mostly hits cache.
_CACHE_TTL = 10 * 60


class VerdictMatrixCache(RedisBackedCache):
    """Encoded verdict grid per (test run, columns mode). Sync, matching its caller."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.VERDICT_MATRIX_CACHE,
            cache_name="verdict-matrix",
            ttl=_CACHE_TTL,
        )

    def _key(self, test_run_id: str, columns: Optional[str]) -> str:
        # `columns=none` omits test_ids from the payload -- a different shape, so
        # it gets its own key rather than trying to derive one from the other.
        return f"{_PREFIX}{test_run_id}:{columns or 'full'}"

    def get(self, test_run_id: str, columns: Optional[str]) -> Optional[str]:
        """Raw cached JSON, or ``None`` on a miss (not connected, absent, or expired)."""
        return self._get(self._key(test_run_id, columns))

    def set(self, test_run_id: str, columns: Optional[str], matrix_json: str) -> None:
        self._set(self._key(test_run_id, columns), matrix_json)

    def get_matrix(self, test_run_id: str, columns: Optional[str]) -> Optional[VerdictMatrix]:
        """Cached matrix, or ``None`` on a miss.

        An entry that no longer parses (written before a ``VerdictMatrix`` schema
        change) counts as a miss: the caller recomputes and overwrites it, so a
        cache-shape problem never surfaces as a failed grid.
        """
        cached = self.get(test_run_id, columns)
        if cached is None:
            return None
        try:
            return VerdictMatrix.model_validate_json(cached)
        except ValidationError:
            logger.warning(
                "%s: discarding unparseable entry for run %s", self._cache_name, test_run_id
            )
            return None

    def set_matrix(self, test_run_id: str, columns: Optional[str], matrix: VerdictMatrix) -> None:
        self.set(test_run_id, columns, matrix.model_dump_json())

    def invalidate(self, test_run_id: str) -> None:
        """Drop both columns-mode entries for this run -- call after any write that
        can change its verdicts, overrides, or review count (see module docstring).
        """
        self._delete(self._key(test_run_id, None), self._key(test_run_id, "none"))


_cache = VerdictMatrixCache()


def get_verdict_matrix_cache() -> VerdictMatrixCache:
    """The process-wide verdict matrix cache. Connects on first use, not on import."""
    _cache.initialize()
    return _cache
