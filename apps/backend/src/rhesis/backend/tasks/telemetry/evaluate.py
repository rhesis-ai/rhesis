"""Celery tasks for trace metrics evaluation.

Two-phase evaluation:
  Phase 1 (evaluate_turn_trace_metrics) - immediate, per-turn
  Phase 2 (evaluate_conversation_trace_metrics) - debounced, per-conversation
"""

import logging
import random
import time
from typing import Any, Dict, List, Optional

from celery import shared_task
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.database import SessionLocal, set_session_variables
from rhesis.backend.app.schemas.metric import MetricScope

logger = logging.getLogger(__name__)

CONVERSATION_INPUT_KEY = "rhesis.conversation.input"
CONVERSATION_OUTPUT_KEY = "rhesis.conversation.output"


def _get_trace_metrics_config(project: models.Project) -> Dict[str, Any]:
    """Extract trace_metrics config from project attributes.

    Returns defaults when attributes are absent or incomplete.
    """
    attrs = project.attributes or {}
    return attrs.get("trace_metrics", {})


def _should_evaluate(config: Dict[str, Any]) -> bool:
    """Check if trace metrics evaluation is enabled and passes sampling."""
    if config.get("enabled") is False:
        return False

    sampling_rate = config.get("sampling_rate", 1.0)
    if sampling_rate < 1.0 and random.random() > sampling_rate:
        return False

    return True


def _load_trace_scoped_metrics(
    db: Session,
    organization_id: str,
    config: Dict[str, Any],
    phase: str = "all",
) -> List[models.Metric]:
    """Load metrics that have 'Trace' in their metric_scope.

    Args:
        phase: Controls adaptive scoping based on documentation rules:
            - "all": Return all Trace-scoped metrics (used for single-turn traces)
            - "turn": Return only metrics explicitly scoped to Single-Turn
            - "conversation": Return metrics scoped to Multi-Turn OR
                              "adaptive" metrics (only scoped to Trace)
        config: Project trace_metrics config. If metric_ids is set,
            filter to those specific metrics only.
    """
    from sqlalchemy import and_, not_, or_

    query = db.query(models.Metric).filter(
        models.Metric.organization_id == organization_id,
        models.Metric.deleted_at.is_(None),
        models.Metric.metric_scope.contains([MetricScope.TRACE.value]),
    )

    metric_ids = config.get("metric_ids")
    if metric_ids:
        query = query.filter(models.Metric.id.in_(metric_ids))

    if phase == "turn":
        query = query.filter(models.Metric.metric_scope.contains([MetricScope.SINGLE_TURN.value]))
    elif phase == "conversation":
        # Multi-Turn explicitly, OR Adaptive (Trace only, neither Single-Turn nor Multi-Turn)
        is_multi = models.Metric.metric_scope.contains([MetricScope.MULTI_TURN.value])
        is_adaptive = and_(
            not_(models.Metric.metric_scope.contains([MetricScope.SINGLE_TURN.value])),
            not_(models.Metric.metric_scope.contains([MetricScope.MULTI_TURN.value])),
        )
        query = query.filter(or_(is_multi, is_adaptive))

    return query.all()


def _derive_status_id(
    db: Session,
    organization_id: str,
    metrics_results: Dict[str, Any],
) -> Optional[str]:
    """Derive trace_metrics_status_id from metric results.

    All metrics must pass for overall Pass. Any failure -> Fail.
    Empty results or errors -> Error.
    """
    metrics = metrics_results.get("metrics", {})
    if not metrics:
        return _resolve_status_id(db, organization_id, TestResultStatus.ERROR.value)

    all_pass = all(m.get("is_successful", False) for m in metrics.values())
    status_name = TestResultStatus.PASS.value if all_pass else TestResultStatus.FAIL.value
    return _resolve_status_id(db, organization_id, status_name)


def _derive_combined_status_id(
    db: Session,
    organization_id: str,
    span: models.Trace,
    new_section: str,
    new_results: Dict[str, Any],
) -> Optional[str]:
    """Re-derive status from combined turn + conversation metrics on a span."""
    existing = span.trace_metrics or {}
    all_metrics = {}

    for section in ("turn_metrics", "conversation_metrics"):
        data = new_results if section == new_section else existing.get(section, {})
        section_metrics = data.get("metrics", {})
        all_metrics.update(section_metrics)

    if not all_metrics:
        return _resolve_status_id(db, organization_id, TestResultStatus.ERROR.value)

    all_pass = all(m.get("is_successful", False) for m in all_metrics.values())
    status_name = TestResultStatus.PASS.value if all_pass else TestResultStatus.FAIL.value
    return _resolve_status_id(db, organization_id, status_name)


def _resolve_status_id(
    db: Session,
    organization_id: str,
    status_name: str,
) -> Optional[str]:
    """Look up a Status row by name and organization."""
    status = (
        db.query(models.Status)
        .filter(
            models.Status.name == status_name,
            models.Status.organization_id == organization_id,
        )
        .first()
    )
    if not status:
        logger.warning(
            f"Status '{status_name}' not found for org {organization_id}; "
            f"trace_metrics_status will not be set"
        )
        return None
    return str(status.id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def evaluate_turn_trace_metrics(
    self,
    trace_id: str,
    project_id: str,
    organization_id: str,
) -> dict:
    """Phase 1: Immediate per-turn trace metrics evaluation.

    Runs after every enrichment. For turns with conversation_id,
    also schedules a debounced conversation-level evaluation.
    """
    db: Session = SessionLocal()

    try:
        set_session_variables(db, organization_id, "")

        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            logger.warning(f"Project {project_id} not found for trace {trace_id}")
            return {"status": "error", "trace_id": trace_id, "message": "project not found"}

        config = _get_trace_metrics_config(project)
        if not _should_evaluate(config):
            return {"status": "skipped", "trace_id": trace_id}

        root_span = (
            db.query(models.Trace)
            .filter(
                models.Trace.trace_id == trace_id,
                models.Trace.parent_span_id.is_(None),
            )
            .order_by(models.Trace.start_time.desc())
            .first()
        )
        if not root_span:
            logger.warning(f"No root span found for trace {trace_id}")
            return {"status": "no_root_span", "trace_id": trace_id}

        input_text = (root_span.attributes or {}).get(CONVERSATION_INPUT_KEY, "")
        output_text = (root_span.attributes or {}).get(CONVERSATION_OUTPUT_KEY, "")
        if not input_text and not output_text:
            logger.info(f"No input/output attributes on root span for trace {trace_id}")
            return {"status": "no_io", "trace_id": trace_id}

        has_conversation = bool(root_span.conversation_id)

        if has_conversation:
            metrics = _load_trace_scoped_metrics(
                db,
                organization_id,
                config,
                phase="turn",
            )
        else:
            metrics = _load_trace_scoped_metrics(db, organization_id, config, phase="all")

        if not metrics:
            logger.info(f"No Trace-scoped metrics found for trace {trace_id}")
            if has_conversation:
                _schedule_debounced_conversation_eval(trace_id, project_id, organization_id)
            return {"status": "no_metrics", "trace_id": trace_id}

        from rhesis.backend.app.utils.user_model_utils import get_user_evaluation_model
        from rhesis.backend.metrics.evaluator import MetricEvaluator

        default_model = None
        project_user = project.owner or project.user
        if project_user:
            try:
                default_model = get_user_evaluation_model(db, project_user)
            except Exception as e:
                logger.warning(f"Failed to get default evaluation model for trace {trace_id}: {e}")

        start_time = time.time()
        evaluator = MetricEvaluator(
            model=default_model,
            db=db,
            organization_id=organization_id,
        )
        results = evaluator.evaluate(
            input_text=input_text,
            output_text=output_text,
            expected_output="",
            context=[],
            metrics=metrics,
        )
        execution_time = (time.time() - start_time) * 1000

        turn_metrics = {
            "execution_time": round(execution_time, 1),
            "metrics": results,
        }

        status_id = _derive_status_id(db, organization_id, turn_metrics)

        crud.update_trace_turn_metrics(
            db=db,
            span_id=str(root_span.id),
            turn_metrics=turn_metrics,
            status_id=status_id,
        )

        logger.info(
            f"Completed turn metrics evaluation for trace {trace_id}: "
            f"{len(turn_metrics.get('metrics', {}))} metrics in {execution_time:.0f}ms"
        )

        if has_conversation:
            _schedule_debounced_conversation_eval(trace_id, project_id, organization_id)

        return {
            "status": "success",
            "trace_id": trace_id,
            "metrics_count": len(turn_metrics.get("metrics", {})),
        }

    except Exception as e:
        logger.error(
            f"Turn metrics evaluation failed for trace {trace_id}: {e}",
            exc_info=True,
        )
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for turn eval of trace {trace_id}")
            return {"status": "error", "trace_id": trace_id, "message": str(e)}

    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def evaluate_conversation_trace_metrics(
    self,
    trace_id: str,
    project_id: str,
    organization_id: str,
) -> dict:
    """Phase 2: Debounced conversation-level trace metrics evaluation.

    Reconstructs the full conversation from all root spans sharing
    the trace_id and evaluates Multi-Turn scoped metrics.
    """
    db: Session = SessionLocal()

    try:
        set_session_variables(db, organization_id, "")

        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            return {"status": "error", "trace_id": trace_id, "message": "project not found"}

        config = _get_trace_metrics_config(project)
        if not _should_evaluate(config):
            return {"status": "skipped", "trace_id": trace_id}

        metrics = _load_trace_scoped_metrics(
            db,
            organization_id,
            config,
            phase="conversation",
        )
        if not metrics:
            logger.info(f"No Multi-Turn Trace metrics found for trace {trace_id}")
            return {"status": "no_metrics", "trace_id": trace_id}

        root_spans = (
            db.query(models.Trace)
            .filter(
                models.Trace.trace_id == trace_id,
                models.Trace.parent_span_id.is_(None),
            )
            .order_by(models.Trace.start_time.asc())
            .all()
        )
        if not root_spans:
            return {"status": "no_spans", "trace_id": trace_id}

        from rhesis.sdk.metrics.conversational.types import ConversationHistory

        messages = []
        for span in root_spans:
            attrs = span.attributes or {}
            input_text = attrs.get(CONVERSATION_INPUT_KEY, "")
            output_text = attrs.get(CONVERSATION_OUTPUT_KEY, "")
            if input_text:
                messages.append({"role": "user", "content": input_text})
            if output_text:
                messages.append({"role": "assistant", "content": output_text})

        if not messages:
            return {"status": "no_conversation", "trace_id": trace_id}

        conversation_history = ConversationHistory.from_messages(messages)
        conversation_text = conversation_history.format_conversation()

        from rhesis.backend.app.utils.user_model_utils import get_user_evaluation_model
        from rhesis.backend.metrics.evaluator import MetricEvaluator

        default_model = None
        project_user = project.owner or project.user
        if project_user:
            try:
                default_model = get_user_evaluation_model(db, project_user)
            except Exception as e:
                logger.warning(f"Failed to get default evaluation model for trace {trace_id}: {e}")

        start_time = time.time()
        evaluator = MetricEvaluator(
            model=default_model,
            db=db,
            organization_id=organization_id,
        )
        results = evaluator.evaluate(
            input_text="",
            output_text=conversation_text.strip(),
            expected_output="",
            context=[],
            metrics=metrics,
            conversation_history=conversation_history,
        )
        execution_time = (time.time() - start_time) * 1000

        conversation_metrics = {
            "execution_time": round(execution_time, 1),
            "metrics": results,
        }

        first_span = root_spans[0]
        status_id = _derive_combined_status_id(
            db,
            organization_id,
            first_span,
            "conversation_metrics",
            conversation_metrics,
        )

        crud.update_trace_conversation_metrics(
            db=db,
            trace_id=trace_id,
            conversation_metrics=conversation_metrics,
            status_id=status_id,
        )

        logger.info(
            f"Completed conversation metrics evaluation for trace {trace_id}: "
            f"{len(conversation_metrics.get('metrics', {}))} metrics "
            f"in {execution_time:.0f}ms"
        )

        return {
            "status": "success",
            "trace_id": trace_id,
            "metrics_count": len(conversation_metrics.get("metrics", {})),
        }

    except Exception as e:
        logger.error(
            f"Conversation metrics evaluation failed for trace {trace_id}: {e}",
            exc_info=True,
        )
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for conversation eval of trace {trace_id}")
            return {"status": "error", "trace_id": trace_id, "message": str(e)}

    finally:
        db.close()


def _schedule_debounced_conversation_eval(
    trace_id: str,
    project_id: str,
    organization_id: str,
) -> None:
    """Schedule/reset the debounced conversation evaluation."""
    try:
        from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
            schedule_conversation_eval,
        )

        schedule_conversation_eval(trace_id, project_id, organization_id)
    except Exception as e:
        logger.warning(f"Failed to schedule conversation eval for trace {trace_id}: {e}")
