import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional

import anyio
from pydantic import BaseModel, Field, create_model
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


class _GeneratedTestSuggestionItem(BaseModel):
    """One LLM-generated test input (shape enforced via structured output)."""

    input: str = Field(..., min_length=1, description="A new diverse test input text")


def _suggestions_response_model(num_suggestions: int) -> type[BaseModel]:
    """Response type requiring exactly ``num_suggestions`` items."""
    return create_model(
        "GeneratedTestSuggestionsResponse",
        __base__=BaseModel,
        suggestions=(
            list[_GeneratedTestSuggestionItem],
            Field(
                ...,
                min_length=num_suggestions,
                max_length=num_suggestions,
                description="New test inputs; count must match the requested number.",
            ),
        ),
    )


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


def _resolve_llm_model(model_or_provider: Any):
    """Ensure we have an SDK BaseLLM instance (not a string id)."""
    from rhesis.sdk.models.factory import get_model

    if isinstance(model_or_provider, str):
        return get_model(model_or_provider, model_type="language")
    return model_or_provider


def _build_suggestion_prompt(
    examples: List[Dict[str, str]],
    topic: str,
    num_suggestions: int,
    user_feedback: str = "",
) -> str:
    """Build a prompt asking the LLM to generate new test inputs."""
    intro = """You are a test generation assistant.
Given example test inputs for an AI system, generate new diverse test inputs."""
    if topic:
        intro += f"\nTarget topic: {topic}"

    example_lines = []
    for i, ex in enumerate(examples, 1):
        example_input = ex.get("input", "")
        example_topic = ex.get("topic", "")
        if example_topic and not topic:
            example_lines.append(
                f"{i}. [topic: {example_topic}] {json.dumps(example_input, ensure_ascii=False)}"
            )
        else:
            example_lines.append(f"{i}. {json.dumps(example_input, ensure_ascii=False)}")

    prompt = f"""{intro}

Example test inputs:
{chr(10).join(example_lines)}"""

    if user_feedback:
        prompt += f"""

Additional guidance from the user:
{user_feedback}"""

    prompt += f"""

Produce exactly {num_suggestions} new test inputs that follow the same overall domain.
Requirements:
- Stay consistent with the target topic when one is provided.
- Do not repeat or lightly paraphrase the example inputs.
- Make each suggestion meaningfully different in scenario, intent, wording, tone, or difficulty.
- Prefer realistic and specific user inputs over generic placeholders.
- Follow the user's additional guidance when possible, but do not break
  the topic or count requirements.
- Return only the requested structured output, with one new input per item."""

    return prompt


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

    model = _resolve_llm_model(_get_generation_model(db, user_id))
    response_model = _suggestions_response_model(num_suggestions)
    topic_value = topic or ""

    try:
        raw_output = model.generate(prompt=prompt_text, schema=response_model)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        raise ValueError(f"LLM generation failed: {e}") from e

    if not isinstance(raw_output, dict):
        raise ValueError("LLM returned unexpected response type (expected structured object)")

    rows = raw_output.get("suggestions") or []
    suggestions = [
        {"topic": topic_value, "input": str(row.get("input", "")).strip()} for row in rows
    ]

    logger.info(
        f"Generated {len(suggestions)} suggestions for "
        f"test_set={test_set_identifier}, topic={topic!r}, "
        f"examples_used={sample_size}"
    )

    return {
        "suggestions": suggestions,
        "num_examples_used": sample_size,
    }


async def invoke_endpoint_for_suggestions_stream(
    db: Session,
    endpoint_id: str,
    suggestions: List[Any],
    organization_id: str,
    user_id: str,
):
    """Stream outputs for non-persisted suggestions as NDJSON bytes.

    Emits per-item events in completion order and finishes with a summary event.

    Event shapes (one JSON object per line):
      - {"type": "item", "index": int, "input": str, "output": str, "error": str|null}
      - {"type": "summary", "generated": int, "total": int}
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

    async def _invoke_one(index: int, input_text: str) -> tuple:
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
                return (index, input_text, output, None)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Suggestion output generation failed: {e}")
                return (index, input_text, "", str(e))

    total = len(suggestions)
    tasks = [
        asyncio.create_task(_invoke_one(i, s.input))  # type: ignore[attr-defined]
        for i, s in enumerate(suggestions)
    ]

    generated = 0
    for fut in asyncio.as_completed(tasks):
        index, input_text, output, error = await fut
        if error is None:
            generated += 1

        event = {
            "type": "item",
            "index": index,
            "input": input_text,
            "output": output,
            "error": error,
        }
        yield (json.dumps(event) + "\n").encode("utf-8")
        await anyio.sleep(0)

    summary = {"type": "summary", "generated": generated, "total": total}
    yield (json.dumps(summary) + "\n").encode("utf-8")


async def evaluate_suggestions_stream(
    db: Session,
    organization_id: str,
    user_id: str,
    metric_names: List[str],
    suggestions: List[Dict[str, str]],
):
    """Stream evaluation results for non-persisted suggestions as NDJSON bytes.

    Emits per-item events in completion order and finishes with a summary event.

    Event shapes (one JSON object per line):
      - {"type": "item", "index": int, "input": str, "label": str, "labeler": str,
         "model_score": float, "metrics": dict|null, "error": str|null}
      - {"type": "summary", "evaluated": int, "total": int}
    """
    sdk_metrics = _resolve_sdk_metrics(db, organization_id, user_id, metric_names)

    async def _evaluate_one(index: int, item: Dict[str, str]) -> tuple:
        input_text = item["input"]
        output_text = item["output"]

        if not output_text or output_text == "[no output]":
            return (
                index,
                {
                    "input": input_text,
                    "label": "",
                    "labeler": "",
                    "model_score": 0.0,
                    "metrics": None,
                    "error": "no output to evaluate",
                },
            )

        try:
            metric_results = await _run_metrics_on_text(sdk_metrics, input_text, output_text)

            valid = {k: v for k, v in metric_results.items() if isinstance(v, dict)}

            if not valid:
                return (
                    index,
                    {
                        "input": input_text,
                        "label": "",
                        "labeler": "",
                        "model_score": 0.0,
                        "metrics": None,
                        "error": "no metric results",
                    },
                )

            all_passed = all(v.get("is_successful", False) for v in valid.values())
            label = "pass" if all_passed else "fail"
            labeler = ", ".join(metric_names)
            scores = [v.get("score", 0.0) for v in valid.values()]
            score = sum(scores) / len(scores) if scores else 0.0
            metrics_summary = build_metrics_summary_for_response(valid)

            return (
                index,
                {
                    "input": input_text,
                    "label": label,
                    "labeler": labeler,
                    "model_score": score,
                    "metrics": metrics_summary,
                    "error": None,
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Suggestion evaluation failed: {e}",
                exc_info=True,
            )
            return (
                index,
                {
                    "input": input_text,
                    "label": "error",
                    "labeler": ", ".join(metric_names),
                    "model_score": 0.0,
                    "metrics": None,
                    "error": str(e),
                },
            )

    semaphore = asyncio.Semaphore(_EVAL_MAX_CONCURRENCY)

    async def _bounded(index: int, item: Dict[str, str]) -> tuple:
        async with semaphore:
            return await _evaluate_one(index, item)

    total = len(suggestions)
    tasks = [asyncio.create_task(_bounded(i, s)) for i, s in enumerate(suggestions)]

    evaluated = 0
    for fut in asyncio.as_completed(tasks):
        index, result = await fut
        if result.get("label") in ("pass", "fail"):
            evaluated += 1

        event = {
            "type": "item",
            "index": index,
            "input": result.get("input", ""),
            "label": result.get("label", ""),
            "labeler": result.get("labeler", ""),
            "model_score": result.get("model_score", 0.0),
            "metrics": result.get("metrics"),
            "error": result.get("error"),
        }
        yield (json.dumps(event) + "\n").encode("utf-8")
        await anyio.sleep(0)

    summary = {"type": "summary", "evaluated": evaluated, "total": total}
    yield (json.dumps(summary) + "\n").encode("utf-8")
