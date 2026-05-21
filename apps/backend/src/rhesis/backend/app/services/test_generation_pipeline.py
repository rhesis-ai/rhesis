"""Streaming test generation pipeline.

Combines config generation and test generation into a single NDJSON stream,
following the same pattern as the explorer suggestion pipeline.
"""

import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import anyio
import jinja2
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import (
    SourceData,
    TestConfigItem,
    TestConfigResponse,
)
from rhesis.backend.app.services.generation import (
    generate_multiturn_tests_stream,
    generate_tests,
    generate_tests_stream,
)
from rhesis.backend.app.services.streaming_utils import IncrementalConfigParser, ndjson
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.synthesizers.config_synthesizer import (
    GenerationConfig as SDKGenerationConfig,
)

logger = logging.getLogger(__name__)

MAX_SAMPLE_SIZE = 6

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _resolve_config_llm(db: Session, user: User):
    """Resolve the LLM for test-config generation (same logic as TestConfigGeneratorService)."""
    gen_settings = getattr(user.settings.models, "generation")
    model_id = gen_settings.model_id
    use_fast_default = False
    if model_id:
        row = crud.get_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
        )
        if row and row.provider_type and row.provider_type.type_value == "polyphemus":
            use_fast_default = True
    if use_fast_default:
        logger.info("User generation model is Polyphemus; using fast default for pipeline config")
        try:
            return get_model(DEFAULT_GENERATION_MODEL)
        except ValueError:
            pass

    user_model = get_user_generation_model(db, user)
    if isinstance(user_model, str):
        try:
            return get_model(user_model, model_type="language")
        except ValueError as e:
            raise ModelConfigurationError(
                f"User model initialization failed: {e}",
                original_error=e,
            ) from e
    return user_model


def _fetch_db_context(
    db: Session,
    organization_id: str,
    prompt: str,
    project_id: Optional[str] = None,
    previous_messages: Optional[list] = None,
) -> Dict[str, Any]:
    """Fetch all DB data needed for config prompts (called once upfront)."""
    behaviors = crud.get_behaviors(db=db, organization_id=organization_id, skip=0, limit=100)
    behavior_list = [{"name": b.name, "description": b.description or ""} for b in behaviors]

    project_name = None
    project_description = None
    if project_id:
        project = crud.get_project(db=db, project_id=project_id, organization_id=organization_id)
        if not project:
            raise ValueError(f"Project with id {project_id} not found or not accessible")
        project_name = project.name
        project_description = project.description

    return {
        "prompt": prompt,
        "sample_size": MAX_SAMPLE_SIZE,
        "behaviors": behavior_list,
        "project_name": project_name,
        "project_description": project_description,
        "previous_messages": previous_messages or [],
    }


def _render_config_prompt(db_context: Dict[str, Any]) -> str:
    """Render the unified config template using pre-fetched DB context."""
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=jinja2.select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = jinja_env.get_template("test_config_generator.jinja2")
    return template.render(db_context)


async def _stream_config(
    llm,
    db_context: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream config items from a single LLM call.

    The LLM returns a JSON object with ``behaviors``, ``topics``, and
    ``categories`` arrays.  ``IncrementalConfigParser`` tracks which key
    each parsed object belongs to so items can be emitted incrementally.

    Yields dicts: ``config_item`` events as they parse,
    then ``config_done`` and ``_collected`` (internal) when finished.
    """
    collected: Dict[str, List[TestConfigItem]] = {
        "behaviors": [],
        "topics": [],
        "categories": [],
    }

    rendered_prompt = _render_config_prompt(db_context)
    parser = IncrementalConfigParser()

    try:
        token_stream = llm.generate_stream(
            prompt=rendered_prompt,
            schema=TestConfigResponse,
        )
        async for chunk in token_stream:
            for category, obj in parser.feed(chunk):
                name = obj.get("name", "")
                description = obj.get("description", "")
                active = obj.get("active", True)
                if not name:
                    continue

                item = TestConfigItem(name=name, description=description, active=active)
                if category in collected:
                    collected[category].append(item)

                yield {
                    "type": "config_item",
                    "category": category,
                    "name": name,
                    "description": description,
                    "active": active,
                }
                await anyio.sleep(0)
    except Exception as e:
        logger.error("Config streaming failed: %s", e, exc_info=True)
        yield {
            "type": "error",
            "phase": "config",
            "message": str(e),
        }
        yield {"type": "config_done", "total": 0}
        yield {"type": "_collected", "config": None}
        return

    total = sum(len(v) for v in collected.values())
    yield {"type": "config_done", "total": total}

    yield {
        "type": "_collected",
        "config": TestConfigResponse(
            behaviors=collected["behaviors"],
            topics=collected["topics"],
            categories=collected["categories"],
        ),
    }


async def test_generation_pipeline_stream(
    db: Session,
    user: User,
    prompt: str,
    organization_id: str,
    project_id: Optional[str] = None,
    previous_messages: Optional[list] = None,
    test_type: str = "single_turn",
    num_tests: int = 5,
    sources: Optional[List[SourceData]] = None,
    model_id: Optional[str] = None,
    config: Optional[TestConfigResponse] = None,
) -> AsyncGenerator[bytes, None]:
    """Unified NDJSON stream: generate config, then generate tests.

    When *config* is supplied, Phase 1 (config generation) is skipped
    and the provided config is used directly for test generation.

    Event protocol (one JSON object per line):
      - ``{"type": "config_item", "category": str, "name": str,
             "description": str, "active": bool}``
      - ``{"type": "config_done", "total": int}``
      - ``{"type": "test", "index": int, "test": dict, "test_type": str}``
      - ``{"type": "tests_done", "total": int}``
      - ``{"type": "error", "phase": str, "message": str}``
      - ``{"type": "done"}``
    """

    config_response: Optional[TestConfigResponse] = config

    if config_response is None:
        # ── Phase 1: Streamed config generation ──

        llm = _resolve_config_llm(db, user)
        db_context = _fetch_db_context(
            db=db,
            organization_id=organization_id,
            prompt=prompt,
            project_id=project_id,
            previous_messages=previous_messages,
        )

        async for event in _stream_config(llm, db_context):
            if event.get("type") == "_collected":
                config_response = event["config"]
                continue
            yield ndjson(event)
            await anyio.sleep(0)

    # ── Phase 2: Test generation ──

    if config_response is None:
        yield ndjson({"type": "error", "phase": "tests", "message": "Config generation failed"})
        yield ndjson({"type": "done"})
        return

    active_behaviors = [b.name for b in config_response.behaviors if b.active]
    active_topics = [t.name for t in config_response.topics if t.active]
    active_categories = [c.name for c in config_response.categories if c.active]

    if not active_behaviors:
        active_behaviors = [b.name for b in config_response.behaviors[:1]]

    test_index = 0
    tests_generated = 0

    try:
        if test_type == "multi_turn":
            config_dict = {
                "generation_prompt": prompt,
                "behaviors": active_behaviors,
                "categories": active_categories,
                "topics": active_topics,
            }
            async for test in generate_multiturn_tests_stream(
                db=db,
                user=user,
                config=config_dict,
                num_tests=num_tests,
                model_id=model_id,
            ):
                yield ndjson(
                    {
                        "type": "test",
                        "index": test_index,
                        "test": test,
                        "test_type": "multi_turn",
                    }
                )
                test_index += 1
                tests_generated += 1
                await anyio.sleep(0)
        elif sources:
            generation_prompt = (
                f"Generate {num_tests} single interaction test cases for: "
                f"{prompt or 'general testing'}"
            )
            sdk_config = SDKGenerationConfig(
                generation_prompt=generation_prompt,
                behaviors=active_behaviors,
                categories=active_categories,
                topics=active_topics,
            )
            tests = await generate_tests(
                db=db,
                user=user,
                config=sdk_config,
                num_tests=num_tests,
                sources=sources,
                model_id=model_id,
            )
            for test in tests:
                yield ndjson(
                    {
                        "type": "test",
                        "index": test_index,
                        "test": test,
                        "test_type": "single_turn",
                    }
                )
                test_index += 1
                tests_generated += 1
                await anyio.sleep(0)
        else:
            generation_prompt = (
                f"Generate {num_tests} single interaction test cases for: "
                f"{prompt or 'general testing'}"
            )
            sdk_config = SDKGenerationConfig(
                generation_prompt=generation_prompt,
                behaviors=active_behaviors,
                categories=active_categories,
                topics=active_topics,
            )
            async for test in generate_tests_stream(
                db=db,
                user=user,
                config=sdk_config,
                num_tests=num_tests,
                model_id=model_id,
            ):
                yield ndjson(
                    {
                        "type": "test",
                        "index": test_index,
                        "test": test,
                        "test_type": "single_turn",
                    }
                )
                test_index += 1
                tests_generated += 1
                await anyio.sleep(0)

    except Exception as e:
        logger.error("Test generation failed at index %d: %s", test_index, e, exc_info=True)
        yield ndjson({"type": "error", "phase": "tests", "message": str(e)})

    yield ndjson({"type": "tests_done", "total": tests_generated})
    yield ndjson({"type": "done"})
