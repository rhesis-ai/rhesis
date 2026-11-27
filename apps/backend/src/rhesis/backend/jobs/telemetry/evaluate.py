"""Celery tasks for trace metrics evaluation.

Every project trace metric is judged once, when its target can be: turn and per-span
targets as each turn arrives (evaluate_turn_trace_metrics), and in a conversation the
``conversation`` and ``run`` targets once it has gone quiet
(evaluate_conversation_trace_metrics, debounced). A trace with no conversation is judged
whole as its turn arrives. ``judged_in_phase`` holds the rule.
"""

import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import TRACE_SKIPPED_STATUS, EntityType
from rhesis.backend.app.crud.telemetry import (
    update_trace_conversation_metrics,
    update_trace_turn_metrics,
)
from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.app.services.telemetry.evaluation_context import (
    CONVERSATION_PHASE,
    TRACE_PHASE,
    TURN_PHASE,
    build_evaluator,
    merge_metric_results,
    project_metric_configs,
)
from rhesis.backend.app.services.telemetry.evaluation_trace import load_evaluation_trace
from rhesis.backend.app.services.telemetry.trace_metrics_config import (
    evaluation_enabled,
    project_trace_metrics_config,
)
from rhesis.backend.app.services.test_result_status import test_result_status_id
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.celery.core import app
from rhesis.backend.metrics.applicability import without_text
from rhesis.backend.metrics.inputs import ResponseTrace, TraceLoader
from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics.arguments import judged_input_output

logger = logging.getLogger(__name__)

CONVERSATION_INPUT_KEY = "rhesis.conversation.input"
CONVERSATION_OUTPUT_KEY = "rhesis.conversation.output"


def _should_evaluate(config: Optional[Dict[str, Any]]) -> bool:
    """Check if the project assigned trace metrics, has evaluation on, and passes sampling."""
    if not evaluation_enabled(config):
        return False

    sampling_rate = config.get("sampling_rate", 1.0)
    if sampling_rate < 1.0 and random.random() > sampling_rate:
        return False

    return True


def _outcome_from_metrics(
    db: Session,
    organization_id: str,
    metrics: Dict[str, Any],
) -> Tuple[Optional[str], str, Optional[str]]:
    """Classify metrics into (status_id, execution, verdict) for a trace.

    Thin wrapper over the single classifier in app/outcomes.py -- see
    playground/outcome-model/inventory.md section 4.1 for the duplicated
    copies of this rule this one replaces. All three are returned together
    so a writer cannot persist the legacy status name without the
    execution/verdict pair that is now the source of truth.
    """
    from rhesis.backend.app.outcomes import (
        classify_metrics,
        outcome_of,
        outcome_to_test_result_status_name,
    )

    execution, verdict = classify_metrics(metrics)
    status_name = outcome_to_test_result_status_name(outcome_of(execution, verdict))
    status_id = _resolve_status_id(db, organization_id, status_name)
    return status_id, execution.value, verdict.value if verdict else None


def _derive_outcome(
    db: Session,
    organization_id: str,
    metrics_results: Dict[str, Any],
) -> Tuple[Optional[str], str, Optional[str]]:
    """Outcome for a single metrics section (turn metrics on their own)."""
    return _outcome_from_metrics(db, organization_id, metrics_results.get("metrics", {}))


def _derive_combined_outcome(
    db: Session,
    organization_id: str,
    span: models.Trace,
    new_section: str,
    new_results: Dict[str, Any],
) -> Tuple[Optional[str], str, Optional[str]]:
    """Re-derive the outcome from combined turn + conversation metrics."""
    existing = span.trace_metrics or {}
    all_metrics = {}

    for section in ("turn_metrics", "conversation_metrics"):
        data = new_results if section == new_section else existing.get(section, {})
        section_metrics = data.get("metrics", {})
        all_metrics.update(section_metrics)

    return _outcome_from_metrics(db, organization_id, all_metrics)


def _resolve_status_id(
    db: Session,
    organization_id: str,
    status_name: str,
) -> Optional[str]:
    """Get or create the Status row for this org/name, scoped to TestResult
    -- the same vocabulary trace_metrics_status borrows from test results.
    get_or_create_status rather than a bare lookup: a status like
    "Inconclusive" may not have been created for this org yet if no
    TestResult has produced one, and this must not silently drop the
    trace's status in that case.
    """

    try:
        return test_result_status_id(db, organization_id, status_name)
    except ValueError:
        logger.warning(
            f"Status '{status_name}' not found for org {organization_id}; "
            f"trace_metrics_status will not be set"
        )
        return None


def _turn_root_span(db: Session, trace_id: str, root_span_id: Optional[str]):
    """The root span a turn evaluation targets: *root_span_id*, else the latest one."""
    query = db.query(models.Trace).filter(models.Trace.parent_span_id.is_(None))
    if root_span_id:
        return query.filter(models.Trace.id == root_span_id).first()
    return (
        query.filter(models.Trace.trace_id == trace_id)
        .order_by(models.Trace.start_time.desc())
        .first()
    )


def _conversation_root_spans(db: Session, trace_id: str) -> List[models.Trace]:
    return (
        db.query(models.Trace)
        .filter(models.Trace.trace_id == trace_id, models.Trace.parent_span_id.is_(None))
        .order_by(models.Trace.start_time.asc())
        .all()
    )


def _mark_skipped_at_token_limit(db: Session, organization_id: str, spans) -> None:
    """Show these spans as not evaluated because of the token limit.

    A span that already has a status (an earlier result or a reviewer's verdict)
    keeps it.
    """
    pending = [span for span in spans if span is not None and span.trace_metrics_status_id is None]
    if not pending:
        return
    status = get_or_create_status(
        db, TRACE_SKIPPED_STATUS, EntityType.TRACE, organization_id=organization_id
    )
    for span in pending:
        span.trace_metrics_status_id = status.id
    db.commit()


def _load_evaluation_config(
    db: Session, trace_id: str, organization_id: str, project_id: str
) -> Optional[Dict[str, Any]]:
    """The project's trace metrics config, or None when evaluation is off (or sampled out)."""
    config = project_trace_metrics_config(db, organization_id, project_id)
    if config is None:
        logger.warning(f"Project {project_id} not found for trace {trace_id}")
        return None
    if not _should_evaluate(config):
        return None
    return config


def _turn_trace_loader(
    trace_id: str, span_id: str, organization_id: str, project_id: str
) -> TraceLoader:
    """Reads one turn's trace. The turns of a conversation share a trace id, so the stored
    trace holds every turn; only this turn's root is kept."""

    def load() -> Optional[Trace]:
        trace = load_evaluation_trace(trace_id, organization_id, project_id)
        if trace is None:
            return None
        trace.root_spans = [root for root in trace.root_spans if root.span_id == span_id]
        return trace

    return load


def _judge(
    evaluator: Any,
    metric_configs: List[Any],
    invalid_metrics: Dict[str, Any],
    trace: Any,
) -> Dict[str, Any]:
    """One phase's results as stored on the span: the metrics and how long they took."""
    start_time = time.time()
    results = merge_metric_results(evaluator.evaluate(metric_configs, trace), invalid_metrics)
    return {
        "execution_time": round((time.time() - start_time) * 1000, 1),
        "metrics": results,
    }


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def evaluate_turn_trace_metrics(
    self,
    trace_id: str,
    project_id: str,
    organization_id: str,
    root_span_id: Optional[str] = None,
) -> dict:
    """Evaluate the trace metrics one stored turn can be judged with.

    Queued once per root span, only for projects with trace metrics, by
    ``EnrichmentService.dispatch_for_spans`` (the spans were enriched when stored). In a
    conversation these are the turn and per-span targets, and the turn also schedules the
    debounced conversation evaluation. A trace with no conversation is the whole run, so
    every metric but ``conversation`` is judged here.

    Args:
        root_span_id: DB primary key of the root span to evaluate.
            When provided the task targets that exact span, avoiding
            a race where the ``trace_id``-based fallback query picks
            up a newer turn in the same conversation.  ``None`` falls
            back to the legacy latest-root-span query for backward
            compatibility with in-flight tasks during deploy.
    """
    db: Session = SessionLocal()

    try:
        bind_scope_to_session(db, organization_id, "", project_id)

        config = _load_evaluation_config(db, trace_id, organization_id, project_id)
        if config is None:
            return {"status": "skipped", "trace_id": trace_id}

        root_span = _turn_root_span(db, trace_id, root_span_id)
        if not root_span:
            logger.warning(f"No root span found for trace {trace_id}")
            return {"status": "no_root_span", "trace_id": trace_id}

        # Skip if turn metrics were already evaluated for this specific span.
        # trace_metrics_processed_at is only set after a real evaluation, not after a
        # skipped one, so a skipped span still gets a second chance.
        if root_span.trace_metrics_processed_at and (root_span.trace_metrics or {}).get(
            "turn_metrics"
        ):
            logger.debug(
                f"Turn metrics already evaluated for span {root_span.id} "
                f"(trace {trace_id}), skipping"
            )
            return {"status": "already_evaluated", "trace_id": trace_id}

        input_text = (root_span.attributes or {}).get(CONVERSATION_INPUT_KEY, "")
        output_text = (root_span.attributes or {}).get(CONVERSATION_OUTPUT_KEY, "")

        has_conversation = bool(root_span.conversation_id)
        metric_configs, invalid_metrics = project_metric_configs(
            db,
            organization_id,
            project_id,
            config,
            TURN_PHASE if has_conversation else TRACE_PHASE,
        )

        if not (metric_configs or invalid_metrics):
            logger.info(f"No project trace metrics apply to trace {trace_id}")
            if has_conversation:
                _schedule_debounced_conversation_eval(trace_id, project_id, organization_id)
            return {"status": "no_metrics", "trace_id": trace_id}

        try:
            evaluator = build_evaluator(db, project_id, trace_id, organization_id)
        except QuotaExceededError as e:
            logger.info(f"Skipping trace {trace_id} evaluation: {e}")
            _mark_skipped_at_token_limit(db, organization_id, [root_span])
            if has_conversation:
                _schedule_debounced_conversation_eval(trace_id, project_id, organization_id)
            return {"status": "quota_exceeded", "trace_id": trace_id}

        # End the read transaction so the connection goes back to the pool for the trace
        # read and the judge calls; the writes below open a new one (GUCs re-applied on begin).
        db.commit()
        loader = _turn_trace_loader(trace_id, str(root_span.span_id), organization_id, project_id)
        if input_text or output_text:
            trace = ResponseTrace(input=input_text, output=output_text, loader=loader)
        else:
            # Not called through Rhesis: the turn is what the trace itself recorded.
            trace = loader()
            if trace is None or not trace.root_spans:
                logger.warning(f"No stored spans to evaluate for trace {trace_id}")
                return {"status": "no_root_span", "trace_id": trace_id}
            if not any(judged_input_output(trace)):
                metric_configs, untextual = without_text(metric_configs)
                invalid_metrics = {**invalid_metrics, **untextual}
        turn_metrics = _judge(evaluator, metric_configs, invalid_metrics, trace)

        status_id, execution, verdict = _derive_outcome(db, organization_id, turn_metrics)

        update_trace_turn_metrics(
            db=db,
            span_id=str(root_span.id),
            turn_metrics=turn_metrics,
            status_id=status_id,
            execution=execution,
            verdict=verdict,
        )

        logger.info(
            f"Completed turn metrics evaluation for trace {trace_id}: "
            f"{len(turn_metrics['metrics'])} metrics in {turn_metrics['execution_time']:.0f}ms"
        )

        if has_conversation:
            _schedule_debounced_conversation_eval(trace_id, project_id, organization_id)

        return {
            "status": "success",
            "trace_id": trace_id,
            "metrics_count": len(turn_metrics.get("metrics", {})),
        }

    except (IOError, ConnectionError, SoftTimeLimitExceeded, OSError) as e:
        logger.warning(f"Transient error in turn eval for trace {trace_id}: {e}")
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(
            f"Turn metrics evaluation failed for trace {trace_id}: {e}",
            exc_info=True,
        )
        raise

    finally:
        db.close()


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def evaluate_conversation_trace_metrics(
    self,
    trace_id: str,
    project_id: str,
    organization_id: str,
) -> dict:
    """Evaluate a conversation's whole-trace metrics once it has gone quiet (debounced).

    A conversation is one trace id with one root span per turn (the SDK, the invoker and
    OTLP ingest all file it so), so the stored trace holds every turn. Judges the metrics
    targeting ``conversation`` or ``run``.
    """
    db: Session = SessionLocal()

    try:
        bind_scope_to_session(db, organization_id, "", project_id)

        config = _load_evaluation_config(db, trace_id, organization_id, project_id)
        if config is None:
            return {"status": "skipped", "trace_id": trace_id}

        metric_configs, invalid_metrics = project_metric_configs(
            db, organization_id, project_id, config, CONVERSATION_PHASE
        )
        if not (metric_configs or invalid_metrics):
            logger.info(f"No conversation project trace metrics for trace {trace_id}")
            return {"status": "no_metrics", "trace_id": trace_id}

        root_spans = _conversation_root_spans(db, trace_id)
        if not root_spans:
            return {"status": "no_spans", "trace_id": trace_id}

        trace = load_evaluation_trace(trace_id, organization_id, project_id)
        if trace is None or not trace.messages().messages:
            return {"status": "no_conversation", "trace_id": trace_id}
        trace.conversation_id = root_spans[0].conversation_id

        try:
            evaluator = build_evaluator(db, project_id, trace_id, organization_id)
        except QuotaExceededError as e:
            logger.info(f"Skipping conversation {trace_id} evaluation: {e}")
            _mark_skipped_at_token_limit(db, organization_id, root_spans)
            return {"status": "quota_exceeded", "trace_id": trace_id}

        # End the read transaction so the connection goes back to the pool for the
        # judge calls; the writes below open a new one (GUCs re-applied on begin).
        db.commit()
        conversation_metrics = _judge(evaluator, metric_configs, invalid_metrics, trace)

        first_span = root_spans[0]
        status_id, execution, verdict = _derive_combined_outcome(
            db,
            organization_id,
            first_span,
            "conversation_metrics",
            conversation_metrics,
        )

        update_trace_conversation_metrics(
            db=db,
            trace_id=trace_id,
            conversation_metrics=conversation_metrics,
            status_id=status_id,
            execution=execution,
            verdict=verdict,
        )

        logger.info(
            f"Completed conversation metrics evaluation for trace {trace_id}: "
            f"{len(conversation_metrics['metrics'])} metrics "
            f"in {conversation_metrics['execution_time']:.0f}ms"
        )

        return {
            "status": "success",
            "trace_id": trace_id,
            "metrics_count": len(conversation_metrics.get("metrics", {})),
        }

    except (IOError, ConnectionError, SoftTimeLimitExceeded, OSError) as e:
        logger.warning(f"Transient error in conversation eval for trace {trace_id}: {e}")
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(
            f"Conversation metrics evaluation failed for trace {trace_id}: {e}",
            exc_info=True,
        )
        raise

    finally:
        db.close()


def _schedule_debounced_conversation_eval(
    trace_id: str,
    project_id: str,
    organization_id: str,
) -> None:
    """Schedule/reset the debounced conversation evaluation.

    Skips scheduling when the conversation has already been marked
    complete (e.g. by Penelope finishing a multi-turn test), since
    an immediate evaluation was already dispatched.
    """
    try:
        from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
            is_conversation_complete,
            schedule_conversation_eval,
        )

        if is_conversation_complete(trace_id, project_id, organization_id):
            logger.debug(
                f"Conversation {trace_id} already marked complete, skipping debounce scheduling"
            )
            return

        schedule_conversation_eval(trace_id, project_id, organization_id)
    except Exception as e:
        logger.warning(f"Failed to schedule conversation eval for trace {trace_id}: {e}")
