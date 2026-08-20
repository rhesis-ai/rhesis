"""When a run that still says ``running`` has stopped being true.

A tuning run claims its slot by writing ``running`` to the summary, and the next
run is refused while that claim stands. The refusal is advisory rather than a
lock -- ADR-0004 accepts that for a flagged feature with one author per metric --
but only the run itself ever clears the claim, which leaves two ways for one to
stay behind forever:

* the worker dies mid-run, so ``fail_tuning_run`` never happens;
* the dispatch straight after the claim raises -- broker unreachable, publish
  error -- so no worker ever picks the run up.

Either way every later run is refused, and the interface disables its own Run
button on the same ``running`` status, so there is no way out from the interface
at all. Recovery meant editing the database.

The escape hatch is a heartbeat, and it is one hatch for both entrances. A run
touches ``progressed_at`` when it claims the slot and again after every case, so
a claim nothing is advancing goes stale and stops refusing anything. The window
only has to cover a single case's evaluation and whatever retries the evaluator
already does -- a forty-case run keeps renewing it -- which is why it can be far
shorter than any whole run.

Staleness is derived here on read and never written: a GET does not repair the
database, and the next run overwrites the summary regardless.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningRunSummary,
    TuningRunStatus,
)

logger = logging.getLogger(__name__)

# How long a claim may go without advancing before anyone may take it over. Per
# case, not per run -- see the module docstring.
STALE_RUN_AFTER = timedelta(minutes=15)

# Phrased to follow the interface's "The last run failed: " rather than repeat it.
STALE_RUN_MESSAGE = "it stopped responding and was abandoned. Press Run to try again."


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """A stored ISO timestamp as an aware datetime, or None if it is not one."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        logger.warning("Unparseable tuning run timestamp %r", value)
        return None
    # Everything written here is UTC and aware; anything else is read as UTC
    # rather than crashing the comparison it is about to be used in.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def run_is_stale(summary: MetricTuningRunSummary, now: Optional[datetime] = None) -> bool:
    """True when this run claims to be running but has stopped advancing."""
    if summary.status != TuningRunStatus.RUNNING:
        return False

    # `progressed_at` is the heartbeat; `started_at` covers a claim written
    # before this rule existed, and stands in until the first case finishes.
    heartbeat = parse_timestamp(summary.progressed_at) or parse_timestamp(summary.started_at)
    if heartbeat is None:
        # A claim with no readable timestamp cannot be shown to be alive, and
        # holding the metric on the strength of it is the wedge itself.
        return True

    return (now or datetime.now(timezone.utc)) - heartbeat > STALE_RUN_AFTER


def abandoned(summary: MetricTuningRunSummary) -> MetricTuningRunSummary:
    """The same run, presented as the failure it turned out to be.

    A copy, because the caller is holding the parsed summary of a live row and
    nothing about reading a run should write one. ``completed_at`` stays unset:
    it never completed.
    """
    stale = summary.model_copy(deep=True)
    stale.status = TuningRunStatus.FAILED
    stale.error = STALE_RUN_MESSAGE
    return stale
