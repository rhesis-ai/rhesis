import asyncio
import json
import logging
import random
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

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


class _IncrementalJsonArrayParser:
    """Extract complete JSON objects from a streaming JSON response.

    Designed for structured output shaped like ``{"suggestions": [{...}, ...]}``.
    Feeds token chunks incrementally and yields each complete object in the
    top-level array as soon as its closing brace is detected.  Correctly
    handles escaped characters and strings containing braces.
    """

    def __init__(self):
        self._buffer: str = ""
        self._pos: int = 0
        self._in_array: bool = False
        self._brace_depth: int = 0
        self._in_string: bool = False
        self._escape_next: bool = False
        self._obj_start: int = -1

    def feed(self, chunk: str) -> List[dict]:
        """Append *chunk* to the internal buffer and return any newly complete objects."""
        self._buffer += chunk
        results: List[dict] = []

        while self._pos < len(self._buffer):
            c = self._buffer[self._pos]

            if self._escape_next:
                self._escape_next = False
                self._pos += 1
                continue

            if c == "\\" and self._in_string:
                self._escape_next = True
                self._pos += 1
                continue

            if c == '"':
                self._in_string = not self._in_string
                self._pos += 1
                continue

            if self._in_string:
                self._pos += 1
                continue

            if not self._in_array:
                if c == "[":
                    self._in_array = True
            else:
                if c == "{":
                    if self._brace_depth == 0:
                        self._obj_start = self._pos
                    self._brace_depth += 1
                elif c == "}":
                    self._brace_depth -= 1
                    if self._brace_depth == 0 and self._obj_start >= 0:
                        obj_str = self._buffer[self._obj_start : self._pos + 1]
                        try:
                            results.append(json.loads(obj_str))
                        except json.JSONDecodeError:
                            logger.warning(
                                "Failed to parse streamed JSON object: %.120s",
                                obj_str,
                            )
                        self._obj_start = -1

            self._pos += 1

        return results


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


def _prepare_suggestion_context(
    db: Session,
    test_set_identifier: str,
    organization_id: str,
    user_id: str,
    topic: Optional[str],
    num_examples: int,
    num_suggestions: int,
    user_feedback: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Shared setup for both streaming and non-streaming suggestion generation.

    Returns a context dict with resolved model, prompt, topic_value, and
    sample_size, or ``None`` when there are no eligible tests.
    """
    db_test_set = crud.resolve_test_set(test_set_identifier, db, organization_id=organization_id)
    if db_test_set is None:
        raise ValueError(f"Test set not found: {test_set_identifier}")

    tests = _get_test_set_tests_from_db(db, db_test_set.id, organization_id, user_id)
    eligible = _build_eligible_tests(tests, topic=topic)

    if not eligible:
        logger.info(
            "No eligible tests for suggestions in test_set=%s, topic=%r",
            test_set_identifier,
            topic,
        )
        return None

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

    return {
        "model": model,
        "response_model": response_model,
        "prompt_text": prompt_text,
        "topic_value": topic or "",
        "sample_size": sample_size,
    }


async def _generate_suggestions_stream(
    ctx: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Async generator that yields suggestion items as they are parsed from
    the LLM token stream.

    Yields
    ------
    dict
        First yield: ``{"type": "meta", "num_examples_used": int}``
        Subsequent yields: ``{"type": "item", "topic": str, "input": str}``
    """
    model = ctx["model"]
    response_model = ctx["response_model"]
    prompt_text = ctx["prompt_text"]
    topic_value = ctx["topic_value"]
    sample_size = ctx["sample_size"]

    yield {"type": "meta", "num_examples_used": sample_size}

    try:
        token_stream = await model.a_generate(
            prompt=prompt_text, schema=response_model, stream=True
        )
    except Exception as e:
        logger.error("LLM streaming generation failed: %s", e, exc_info=True)
        raise ValueError(f"LLM generation failed: {e}") from e

    parser = _IncrementalJsonArrayParser()

    async for chunk in token_stream:
        for item in parser.feed(chunk):
            text = str(item.get("input", "")).strip()
            yield {"type": "item", "topic": topic_value, "input": text}


async def generate_suggestions(
    db: Session,
    test_set_identifier: str,
    organization_id: str,
    user_id: str,
    topic: Optional[str] = None,
    num_examples: int = 10,
    num_suggestions: int = 20,
    user_feedback: Optional[str] = None,
    generate_embeddings: bool = False,
    stream: bool = False,
) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
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
    generate_embeddings : bool
        When True (and ``stream=False``), compute embeddings and sort by
        diversity before returning.  Ignored when ``stream=True`` — the
        caller (pipeline) handles embeddings incrementally.
    stream : bool
        When True, return an async generator yielding individual suggestion
        dicts as they are parsed from the LLM token stream.  The generator
        first yields ``{"type": "meta", "num_examples_used": int}``, then
        ``{"type": "item", "topic": str, "input": str}`` for each item.

    Returns
    -------
    dict (stream=False)
        ``{"suggestions": [...], "num_examples_used": int}``
    AsyncGenerator (stream=True)
        Yields typed dicts as described above.
    """
    ctx = _prepare_suggestion_context(
        db,
        test_set_identifier,
        organization_id,
        user_id,
        topic,
        num_examples,
        num_suggestions,
        user_feedback,
    )

    if ctx is None:
        if stream:

            async def _empty_stream():
                yield {"type": "meta", "num_examples_used": 0}

            return _empty_stream()
        return {"suggestions": [], "num_examples_used": 0}

    if stream:
        return _generate_suggestions_stream(ctx)

    # ── Non-streaming path (unchanged) ──
    model = ctx["model"]
    response_model = ctx["response_model"]
    prompt_text = ctx["prompt_text"]
    topic_value = ctx["topic_value"]
    sample_size = ctx["sample_size"]

    try:
        raw_output = await model.a_generate(prompt=prompt_text, schema=response_model)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        raise ValueError(f"LLM generation failed: {e}") from e

    if not isinstance(raw_output, dict):
        raise ValueError("LLM returned unexpected response type (expected structured object)")

    rows = raw_output.get("suggestions") or []
    suggestions = [
        {"topic": topic_value, "input": str(row.get("input", "")).strip()} for row in rows
    ]

    if generate_embeddings:
        from rhesis.backend.app.services.adaptive_testing.embeddings import (
            a_generate_embedding_vectors_batch,
            resolve_embedder,
            sort_by_diversity,
        )

        embedder = resolve_embedder(db, user_id)
        texts = [(item.get("input") or "").strip() for item in suggestions]

        vectors = await a_generate_embedding_vectors_batch(
            texts,
            db,
            user_id,
            embedder=embedder,
        )
        for item, vec in zip(suggestions, vectors):
            item["embedding"] = vec

        suggestions = sort_by_diversity(suggestions)

    logger.info(
        f"Generated {len(suggestions)} suggestions for "
        f"test_set={test_set_identifier}, topic={topic!r}, "
        f"examples_used={sample_size}"
    )

    return {
        "suggestions": suggestions,
        "num_examples_used": sample_size,
    }


def _ndjson(event: Dict[str, Any]) -> bytes:
    """Encode a single NDJSON event."""
    return (json.dumps(event) + "\n").encode("utf-8")


async def suggestion_pipeline_stream(
    db: Session,
    test_set_identifier: str,
    organization_id: str,
    user_id: str,
    endpoint_id: str,
    metric_names: List[str],
    topic: Optional[str] = None,
    num_examples: int = 10,
    num_suggestions: int = 20,
    user_feedback: Optional[str] = None,
    generate_embeddings: bool = False,
):
    """Unified NDJSON stream: generate, embed, invoke endpoint, evaluate.

    All phases are **fully pipelined**: as each suggestion is parsed from
    the LLM token stream it is immediately emitted, and embedding +
    endpoint invocation + evaluation tasks are spawned concurrently.
    Events of all types interleave naturally as they complete.

    Event protocol (one JSON object per line):
      - ``{"type": "suggestion", "index": int, "topic": str, "input": str}``
      - ``{"type": "embedding", "index": int}``
      - ``{"type": "output", "index": int, "input": str, "output": str,
             "error": str|null}``
      - ``{"type": "evaluation", "index": int, "input": str, "label": str, ...}``
      - ``{"type": "suggestions_done", "total": int, "num_examples_used": int,
             "diversity_order": [int, ...]|null}``
      - ``{"type": "output_summary", "generated": int, "total": int}``
      - ``{"type": "eval_summary", "evaluated": int, "total": int}``
      - ``{"type": "done"}``
    """
    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.dependencies import get_endpoint_service
    from rhesis.backend.tasks.execution.executors.results import process_endpoint_result

    pipeline_t0 = time.monotonic()

    def _ts() -> str:
        elapsed = time.monotonic() - pipeline_t0
        return f"t={elapsed:6.2f}s"

    logger.info("[%s] pipeline_start", _ts())

    suggestion_gen = await generate_suggestions(
        db=db,
        test_set_identifier=test_set_identifier,
        organization_id=organization_id,
        user_id=user_id,
        topic=topic,
        num_examples=num_examples,
        num_suggestions=num_suggestions,
        user_feedback=user_feedback,
        stream=True,
    )

    # ── Resolve services once ──
    svc = get_endpoint_service()
    sdk_metrics = _resolve_sdk_metrics(db, organization_id, user_id, metric_names)

    embedder = None
    if generate_embeddings:
        from rhesis.backend.app.services.adaptive_testing.embeddings import (
            a_generate_embedding_vector,
            resolve_embedder,
        )

        embedder = resolve_embedder(db, user_id)

    # ── Shared state ──
    suggestions: List[Dict[str, Any]] = []
    num_examples_used = 0

    embedding_tasks: Dict[int, asyncio.Task] = {}
    embed_results: Dict[int, Optional[List[float]]] = {}
    invoke_tasks: set = set()
    eval_tasks: set = set()

    output_semaphore = asyncio.Semaphore(10)
    eval_semaphore = asyncio.Semaphore(_EVAL_MAX_CONCURRENCY)
    event_queue: asyncio.Queue = asyncio.Queue()

    outputs_generated = 0
    outputs_failed = 0
    evals_done = 0
    evals_failed = 0

    # ── Background task helpers (all push to the shared event_queue) ──

    async def _embed_one(idx: int, text: str):
        try:
            vec = await a_generate_embedding_vector(text, db, user_id, embedder=embedder)
            embed_results[idx] = vec
            await event_queue.put({"type": "embedding", "index": idx})
        except Exception as e:  # noqa: BLE001
            logger.warning("Embedding failed for suggestion %s: %s", idx, e)
            embed_results[idx] = None
            await event_queue.put({"type": "embedding", "index": idx})

    async def _evaluate_one(index: int, input_text: str, output_text: str):
        nonlocal evals_done, evals_failed
        logger.info("[%s] idx=%02d evaluation_start", _ts(), index)
        async with eval_semaphore:
            try:
                metric_results = await _run_metrics_on_text(
                    sdk_metrics,
                    input_text,
                    output_text,
                )
                valid = {k: v for k, v in metric_results.items() if isinstance(v, dict)}
                if not valid:
                    await event_queue.put(
                        {
                            "type": "evaluation",
                            "index": index,
                            "input": input_text,
                            "label": "",
                            "labeler": "",
                            "model_score": 0.0,
                            "metrics": None,
                            "error": "no metric results",
                        }
                    )
                    evals_failed += 1
                    return

                all_passed = all(v.get("is_successful", False) for v in valid.values())
                label = "pass" if all_passed else "fail"
                labeler = ", ".join(metric_names)
                scores = [v.get("score", 0.0) for v in valid.values()]
                score = sum(scores) / len(scores) if scores else 0.0
                metrics_summary = build_metrics_summary_for_response(valid)

                await event_queue.put(
                    {
                        "type": "evaluation",
                        "index": index,
                        "input": input_text,
                        "label": label,
                        "labeler": labeler,
                        "model_score": score,
                        "metrics": metrics_summary,
                        "error": None,
                    }
                )
                evals_done += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("Pipeline eval failed for index %s: %s", index, e)
                await event_queue.put(
                    {
                        "type": "evaluation",
                        "index": index,
                        "input": input_text,
                        "label": "error",
                        "labeler": ", ".join(metric_names),
                        "model_score": 0.0,
                        "metrics": None,
                        "error": str(e),
                    }
                )
                evals_failed += 1
            finally:
                logger.info("[%s] idx=%02d evaluation_stop", _ts(), index)

    async def _invoke_one(index: int, input_text: str):
        nonlocal outputs_generated, outputs_failed
        logger.info("[%s] idx=%02d output_start", _ts(), index)
        async with output_semaphore:
            try:
                with get_db_with_tenant_variables(organization_id, user_id) as task_db:
                    raw = await svc.invoke_endpoint(
                        db=task_db,
                        endpoint_id=endpoint_id,
                        input_data={"input": input_text},
                        organization_id=organization_id,
                        user_id=user_id,
                    )
                processed = process_endpoint_result(raw)
                output = (processed.get("output") or "").strip() or "[no output]"
                error = None
                outputs_generated += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("Pipeline output failed for index %s: %s", index, e)
                output = ""
                error = str(e)
                outputs_failed += 1

        logger.info("[%s] idx=%02d output_stop", _ts(), index)

        await event_queue.put(
            {
                "type": "output",
                "index": index,
                "input": input_text,
                "output": output,
                "error": error,
            }
        )

        if not error and output and output != "[no output]":
            task = asyncio.create_task(_evaluate_one(index, input_text, output))
            eval_tasks.add(task)
            task.add_done_callback(eval_tasks.discard)

    # ── Stream suggestions, immediately spawning all background work ──

    suggestion_index = 0
    logger.info("[%s] idx=%02d generation_start", _ts(), suggestion_index)

    async for event in suggestion_gen:
        if event.get("type") == "meta":
            num_examples_used = event.get("num_examples_used", 0)
            continue

        text = (event.get("input") or "").strip()
        topic_val = event.get("topic", "")
        idx = suggestion_index
        suggestion_index += 1
        suggestion = {"topic": topic_val, "input": text}
        suggestions.append(suggestion)

        logger.info("[%s] idx=%02d generation_stop", _ts(), idx)
        if idx < num_suggestions - 1:
            logger.info("[%s] idx=%02d generation_start", _ts(), idx + 1)

        yield _ndjson({"type": "suggestion", "index": idx, "topic": topic_val, "input": text})
        await anyio.sleep(0)

        # Spawn embedding task
        if embedder and text:
            task = asyncio.create_task(_embed_one(idx, text))
            embedding_tasks[idx] = task

        # Spawn endpoint invocation immediately
        if text:
            t = asyncio.create_task(_invoke_one(idx, text))
            invoke_tasks.add(t)
            t.add_done_callback(invoke_tasks.discard)

        # Drain any ready events (embedding, output, evaluation)
        while not event_queue.empty():
            yield _ndjson(await event_queue.get())
            await anyio.sleep(0)

    logger.info("[%s] all generation_stop (%d suggestions)", _ts(), len(suggestions))

    # ── Drain all remaining background work ──
    # Embedding tasks, invoke tasks, and eval tasks all push to event_queue.
    all_bg_tasks = set(embedding_tasks.values()) | invoke_tasks | eval_tasks

    while all_bg_tasks or not event_queue.empty():
        while not event_queue.empty():
            yield _ndjson(await event_queue.get())
            await anyio.sleep(0)
        # Recompute live set (eval_tasks grow dynamically from _invoke_one)
        all_bg_tasks = set(embedding_tasks.values()) | invoke_tasks | eval_tasks
        live = {t for t in all_bg_tasks if not t.done()}
        if live:
            await asyncio.wait(live, timeout=0.2, return_when=asyncio.FIRST_COMPLETED)
        elif not event_queue.empty():
            continue
        else:
            break

    # Final flush
    while not event_queue.empty():
        yield _ndjson(await event_queue.get())
        await anyio.sleep(0)

    # ── suggestions_done with diversity order ──
    diversity_order: Optional[List[int]] = None
    if generate_embeddings and suggestions:
        from rhesis.backend.app.services.adaptive_testing.embeddings import (
            sort_by_diversity,
        )

        items_for_sort: List[Dict[str, Any]] = []
        for i, s in enumerate(suggestions):
            entry = dict(s)
            entry["embedding"] = embed_results.get(i)
            entry["_original_idx"] = i
            items_for_sort.append(entry)

        sorted_items = sort_by_diversity(items_for_sort)
        diversity_order = [item["_original_idx"] for item in sorted_items]

    yield _ndjson(
        {
            "type": "suggestions_done",
            "total": len(suggestions),
            "num_examples_used": num_examples_used,
            "diversity_order": diversity_order,
        }
    )
    await anyio.sleep(0)

    # ── Summaries ──
    total = len([s for s in suggestions if (s.get("input") or "").strip()])
    logger.info(
        "[%s] pipeline_stop — outputs=%d/%d, evals=%d/%d, output_failures=%d, eval_failures=%d",
        _ts(),
        outputs_generated,
        total,
        evals_done,
        outputs_generated,
        outputs_failed,
        evals_failed,
    )
    yield _ndjson(
        {
            "type": "output_summary",
            "generated": outputs_generated,
            "total": total,
        }
    )
    yield _ndjson(
        {
            "type": "eval_summary",
            "evaluated": evals_done,
            "total": outputs_generated,
        }
    )
    yield _ndjson({"type": "done"})


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
