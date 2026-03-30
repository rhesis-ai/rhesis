import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud

from .evaluation import (
    _EVAL_MAX_CONCURRENCY,
    _resolve_sdk_metrics,
    _run_metrics_on_text,
    build_metrics_summary_for_response,
)
from .utils import _build_eligible_tests, _get_test_set_tests_from_db

logger = logging.getLogger(__name__)


def _get_generation_model(db: Session, user_id: str):
    """Get the user's configured generation model for suggestion generation."""
    from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
    from rhesis.backend.app.utils.user_model_utils import (
        get_user_generation_model,
    )

    try:
        user = crud.get_user_by_id(db, user_id)
        if user:
            return get_user_generation_model(db, user)
    except Exception as e:
        logger.warning(f"Error fetching user generation model: {e}")

    from rhesis.sdk.models.factory import get_model

    return get_model(DEFAULT_GENERATION_MODEL)


def _build_suggestion_prompt(
    examples: List[Dict[str, str]],
    topic: str,
    num_suggestions: int,
    user_feedback: str = "",
) -> str:
    """Build a prompt asking the LLM to generate new test inputs."""
    lines = [
        "You are a test generation assistant. "
        "Given example test inputs for an AI system, "
        "generate new diverse test inputs.\n"
    ]

    if topic:
        lines.append(f"Topic: {topic}\n")

    lines.append("Example test inputs:")
    for i, ex in enumerate(examples, 1):
        ex_topic = ex.get("topic", "")
        ex_input = ex.get("input", "")
        if ex_topic:
            lines.append(f"{i}. [{ex_topic}] {ex_input}")
        else:
            lines.append(f"{i}. {ex_input}")

    if user_feedback:
        lines.append(f"\nAdditional guidance from the user:\n{user_feedback}\n")

    lines.append(
        f"\nGenerate exactly {num_suggestions} new, diverse test inputs. "
        "Each test input should be on its own line, "
        "prefixed with its number (e.g. '1. ...'). "
        "Output only the numbered list, nothing else."
    )

    return "\n".join(lines)


def _parse_suggestions(raw_text: str, topic: str) -> List[Dict[str, str]]:
    """Parse LLM output into individual suggestion dicts."""
    suggestions: List[Dict[str, str]] = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        if not cleaned:
            continue
        suggestions.append({"topic": topic or "", "input": cleaned})
    return suggestions


def generate_suggestions(
    db: Session,
    test_set_identifier: str,
    organization_id: str,
    user_id: str,
    topic: Optional[str] = None,
    num_examples: int = 10,
    num_suggestions: int = 20,
    user_feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate test suggestions using an LLM.

    Randomly selects existing tests as examples, builds a prompt,
    and asks the LLM to generate new test inputs.

    Parameters
    ----------
    db : Session
        Database session
    test_set_identifier : str
        Test set identifier (UUID, nano_id, or slug)
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    topic : str, optional
        If provided, filter examples and scope suggestions to this topic
    num_examples : int
        Number of existing tests to sample as examples (default 10)
    num_suggestions : int
        Number of new tests to generate (default 20)
    user_feedback : str, optional
        Optional user guidance appended to the LLM prompt

    Returns
    -------
    dict
        - suggestions: list of {topic, input}
        - num_examples_used: how many examples were actually used
    """
    db_test_set = crud.resolve_test_set(test_set_identifier, db, organization_id=organization_id)
    if db_test_set is None:
        raise ValueError(f"Test set not found: {test_set_identifier}")

    tests = _get_test_set_tests_from_db(db, db_test_set.id, organization_id, user_id)

    eligible = _build_eligible_tests(tests, topic=topic)

    if not eligible:
        logger.info(
            f"No eligible tests for suggestions in test_set={test_set_identifier}, topic={topic!r}"
        )
        return {"suggestions": [], "num_examples_used": 0}

    sample_size = min(num_examples, len(eligible))
    sampled = random.sample(eligible, sample_size)

    examples = []
    for t in sampled:
        t_topic = t.topic.name if t.topic and hasattr(t.topic, "name") else ""
        examples.append(
            {
                "topic": t_topic,
                "input": (t.prompt.content or "").strip(),
            }
        )

    feedback_text = (user_feedback or "").strip()
    prompt_text = _build_suggestion_prompt(
        examples, topic or "", num_suggestions, user_feedback=feedback_text
    )

    model = _get_generation_model(db, user_id)

    try:
        raw_output = model.generate(prompt_text)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        raise ValueError(f"LLM generation failed: {e}") from e

    suggestions = _parse_suggestions(raw_output, topic or "")

    logger.info(
        f"Generated {len(suggestions)} suggestions for "
        f"test_set={test_set_identifier}, topic={topic!r}, "
        f"examples_used={sample_size}"
    )

    return {
        "suggestions": suggestions,
        "num_examples_used": sample_size,
    }


async def invoke_endpoint_for_suggestions(
    db: Session,
    endpoint_id: str,
    inputs: List[Dict[str, str]],
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Invoke an endpoint for non-persisted suggestion inputs.

    Similar to generate_outputs_for_tests but operates on raw
    input strings and does not persist results to the database.

    Parameters
    ----------
    db : Session
        Database session
    endpoint_id : str
        Endpoint UUID to invoke
    inputs : list of dict
        Each dict has 'input' (str) and optionally 'topic' (str)
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation

    Returns
    -------
    dict
        - generated: count of successful invocations
        - results: list of {input, output, error}
    """
    from rhesis.backend.app.database import (
        get_db_with_tenant_variables,
    )
    from rhesis.backend.app.dependencies import get_endpoint_service
    from rhesis.backend.tasks.execution.executors.results import (
        process_endpoint_result,
    )

    svc = get_endpoint_service()
    semaphore = asyncio.Semaphore(10)

    async def _invoke_one(
        input_text: str,
    ) -> tuple:
        async with semaphore:
            try:
                with get_db_with_tenant_variables(organization_id, user_id) as task_db:
                    result = await svc.invoke_endpoint(
                        db=task_db,
                        endpoint_id=endpoint_id,
                        input_data={"input": input_text},
                        organization_id=organization_id,
                        user_id=user_id,
                    )
                processed = process_endpoint_result(result)
                output = (processed.get("output") or "").strip() or "[no output]"
                return (input_text, output, None)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Suggestion output generation failed: {e}")
                return (input_text, "", str(e))

    tasks = [_invoke_one(item["input"]) for item in inputs]
    raw_results = await asyncio.gather(*tasks)

    results = []
    generated = 0
    for input_text, output, error in raw_results:
        results.append(
            {
                "input": input_text,
                "output": output,
                "error": error,
            }
        )
        if error is None:
            generated += 1

    logger.info(
        f"Suggestion outputs: endpoint={endpoint_id}, "
        f"generated={generated}, failed={len(inputs) - generated}"
    )

    return {"generated": generated, "results": results}


async def evaluate_suggestions(
    db: Session,
    organization_id: str,
    user_id: str,
    metric_names: List[str],
    suggestions: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Evaluate non-persisted suggestion input/output pairs.

    Uses SDK metric instances directly via ``a_evaluate`` and processes
    up to ``_EVAL_MAX_CONCURRENCY`` suggestions concurrently.

    Parameters
    ----------
    db : Session
        Database session
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    metric_names : list of str
        Metric names to evaluate
    suggestions : list of dict
        Each dict has 'input' and 'output' strings

    Returns
    -------
    dict
        - evaluated: count of successful evaluations
        - results: list of {input, label, labeler, model_score, metrics?, error}
    """
    sdk_metrics = _resolve_sdk_metrics(db, organization_id, user_id, metric_names)

    async def _evaluate_item(item: Dict[str, str]) -> Dict[str, Any]:
        input_text = item["input"]
        output_text = item["output"]

        if not output_text or output_text == "[no output]":
            return {
                "input": input_text,
                "label": "",
                "labeler": "",
                "model_score": 0.0,
                "error": "no output to evaluate",
            }

        try:
            metric_results = await _run_metrics_on_text(sdk_metrics, input_text, output_text)

            valid = {k: v for k, v in metric_results.items() if isinstance(v, dict)}

            if not valid:
                return {
                    "input": input_text,
                    "label": "",
                    "labeler": "",
                    "model_score": 0.0,
                    "error": "no metric results",
                }

            all_passed = all(v.get("is_successful", False) for v in valid.values())
            label = "pass" if all_passed else "fail"
            labeler = ", ".join(metric_names)
            scores = [v.get("score", 0.0) for v in valid.values()]
            score = sum(scores) / len(scores) if scores else 0.0

            metrics_summary = build_metrics_summary_for_response(valid)
            logger.debug(
                "Suggestion evaluation: %s",
                {
                    "input": input_text,
                    "output": output_text,
                    "metrics": metrics_summary,
                },
            )

            return {
                "input": input_text,
                "label": label,
                "labeler": labeler,
                "model_score": score,
                "metrics": metrics_summary,
                "error": None,
            }

        except Exception as e:
            logger.warning(
                f"Suggestion evaluation failed: {e}",
                exc_info=True,
            )
            return {
                "input": input_text,
                "label": "error",
                "labeler": ", ".join(metric_names),
                "model_score": 0.0,
                "error": str(e),
            }

    semaphore = asyncio.Semaphore(_EVAL_MAX_CONCURRENCY)

    async def _bounded(item):
        async with semaphore:
            return await _evaluate_item(item)

    all_results = list(await asyncio.gather(*(_bounded(s) for s in suggestions)))

    evaluated = sum(1 for r in all_results if r.get("label") in ("pass", "fail"))

    logger.info(
        f"Suggestion evaluation: metrics={metric_names!r}, "
        f"evaluated={evaluated}, total={len(suggestions)}"
    )

    return {"evaluated": evaluated, "results": all_results}
