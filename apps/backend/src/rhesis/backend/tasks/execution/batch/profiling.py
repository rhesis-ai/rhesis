"""
Lightweight process-level profiling for batch execution.

Uses ``resource.getrusage(RUSAGE_SELF)`` — zero overhead, no dependencies,
works on Linux (production) and macOS (development).

Note: ``ru_maxrss`` is a high-water mark that only grows within a process
lifetime.  The *growth* between two snapshots still tells you how much a
given batch contributed to peak memory.
"""

import logging
import resource
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_RSS_DIVISOR = 1024 * 1024 if sys.platform == "darwin" else 1024


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
    """Emit a structured batch profiling report via the standard logger."""
    failed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "failed")
    skipped = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "skipped")
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

    logger.info(
        "[BATCH] run=%s tests=%d (ok=%d fail=%d skip=%d) concurrency=%d | "
        "wall=%ss | cpu: user=%ss sys=%ss total=%ss (%s%%) | "
        "mem: peak_rss=%sMB growth=%sMB | ctx_sw: vol=%d invol=%d",
        test_run_id,
        total_tests,
        succeeded,
        failed,
        skipped,
        concurrency,
        wall_s,
        user,
        sys_cpu,
        total_cpu,
        cpu_pct,
        rss_peak,
        rss_growth,
        vol_cs,
        invol_cs,
    )
