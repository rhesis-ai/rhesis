"""
Lightweight process-level profiling for batch execution.

Uses ``resource.getrusage(RUSAGE_SELF)`` — zero overhead, no dependencies,
works on Linux (production) and macOS (development).

Reports are written to a dedicated ``profiling.log`` file (in the working
directory) so they don't get buried in normal worker output.  The same line
is also emitted via the standard logger at INFO level.

Note: ``ru_maxrss`` is a high-water mark that only grows within a process
lifetime.  The *growth* between two snapshots still tells you how much a
given batch contributed to peak memory.
"""

import logging
import os
import resource
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_RSS_DIVISOR = 1024 * 1024 if sys.platform == "darwin" else 1024

_PROFILING_LOG = os.environ.get("RHESIS_PROFILING_LOG", "profiling.log")

_file_logger: logging.Logger | None = None


def _get_file_logger() -> logging.Logger:
    """Lazily create a logger that appends to the dedicated profiling file."""
    global _file_logger
    if _file_logger is None:
        _file_logger = logging.getLogger("rhesis.profiling")
        _file_logger.setLevel(logging.INFO)
        _file_logger.propagate = False
        handler = logging.FileHandler(_PROFILING_LOG, mode="a")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        _file_logger.addHandler(handler)
    return _file_logger


@dataclass
class ResourceSnapshot:
    """Point-in-time capture of process resource counters."""

    user_cpu_s: float
    system_cpu_s: float
    peak_rss_mb: float
    voluntary_ctx_switches: int
    involuntary_ctx_switches: int

    @classmethod
    def take(cls) -> "ResourceSnapshot":
        ru = resource.getrusage(resource.RUSAGE_SELF)
        return cls(
            user_cpu_s=ru.ru_utime,
            system_cpu_s=ru.ru_stime,
            peak_rss_mb=ru.ru_maxrss / _RSS_DIVISOR,
            voluntary_ctx_switches=ru.ru_nvcsw,
            involuntary_ctx_switches=ru.ru_nivcsw,
        )


def log_batch_report(
    *,
    before: ResourceSnapshot,
    after: ResourceSnapshot,
    wall_time_ms: float,
    total_tests: int,
    results: List[Dict[str, Any]],
    concurrency: int,
    test_run_id: str = "",
) -> None:
    """Write a structured report to profiling.log and the standard logger."""
    failed = sum(
        1 for r in results
        if isinstance(r, dict) and r.get("status") == "failed"
    )
    skipped = sum(
        1 for r in results
        if isinstance(r, dict) and r.get("status") == "skipped"
    )
    succeeded = total_tests - failed - skipped

    user = round(after.user_cpu_s - before.user_cpu_s, 2)
    sys_cpu = round(after.system_cpu_s - before.system_cpu_s, 2)
    total_cpu = round(user + sys_cpu, 2)
    rss_peak = round(after.peak_rss_mb)
    rss_growth = round(after.peak_rss_mb - before.peak_rss_mb)
    vol_cs = after.voluntary_ctx_switches - before.voluntary_ctx_switches
    invol_cs = after.involuntary_ctx_switches - before.involuntary_ctx_switches

    wall_s = round(wall_time_ms / 1000, 1)
    cpu_pct = round(total_cpu / (wall_s or 1) * 100, 1)

    line = (
        f"[BATCH] run={test_run_id} "
        f"tests={total_tests} (ok={succeeded} fail={failed} skip={skipped}) "
        f"concurrency={concurrency} | "
        f"wall={wall_s}s | "
        f"cpu: user={user}s sys={sys_cpu}s total={total_cpu}s ({cpu_pct}%) | "
        f"mem: peak_rss={rss_peak}MB growth={rss_growth}MB | "
        f"ctx_sw: vol={vol_cs} invol={invol_cs}"
    )

    logger.info(line)
    _get_file_logger().info(line)
