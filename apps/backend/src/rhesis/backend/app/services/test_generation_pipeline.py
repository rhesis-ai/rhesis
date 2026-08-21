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

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.constants import REQUIREMENT_LIST_KEY, TestSetType
from rhesis.backend.app.crud import model as model_crud
from rhesis.backend.app.crud import requirement as requirement_crud
from rhesis.backend.app.crud.project import get_project
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota.enforcement import stream_error_message
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
from rhesis.backend.app.utils.user_model_utils import (
    ensure_language_model,
    get_user_generation_model,
)
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
        row = model_crud.get_model(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
        )
        if row and row.provider_type and row.provider_type.type_value == "polyphemus":
            use_fast_default = True
    if use_fast_default:
        logger.info("User generation model is Polyphemus; using fast default for pipeline config")
        try:
            # ensure_language_model, not resolve_default_hosted_model: see the
            # note on the identical branch in test_config_generator.py.
            return ensure_language_model(get_model_settings().generation_model)
        except ValueError:
            pass

    try:
        return ensure_language_model(get_user_generation_model(db, user))
    except ValueError as e:
        raise ModelConfigurationError(
            f"User model initialization failed: {e}",
            original_error=e,
        ) from e


def _fetch_db_context(
    db: Session,
    organization_id: str,
    prompt: str,
    project_id: Optional[str] = None,
    previous_messages: Optional[list] = None,
) -> Dict[str, Any]:
    """Fetch all DB data needed for config prompts (called once upfront)."""
    requirements = requirement_crud.get_requirements(
        db=db, organization_id=organization_id, skip=0, limit=100
    )
    requirement_list = [{"name": b.name, "description": b.description or ""} for b in requirements]

    project_name = None
    project_description = None
    if project_id:
        project = get_project(db=db, project_id=project_id, organization_id=organization_id)
        if not project:
            raise ValueError(f"Project with id {project_id} not found or not accessible")
        project_name = project.name
        project_description = project.description

    return {
        "prompt": prompt,
        "sample_size": MAX_SAMPLE_SIZE,
        # Must stay in sync with the `{{ requirements }}` variable in
        # test_config_generator.jinja2 -- the template can't reference this constant.
        REQUIREMENT_LIST_KEY: requirement_list,
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

    The LLM returns a JSON object with ``requirements``, ``topics``, and
    ``categories`` arrays.  ``IncrementalConfigParser`` tracks which key
    each parsed object belongs to so items can be emitted incrementally.

    Yields dicts: ``config_item`` events as they parse,
    then ``config_done`` and ``_collected`` (internal) when finished.
    """
    collected: Dict[str, List[TestConfigItem]] = {
        REQUIREMENT_LIST_KEY: [],
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
            "message": stream_error_message(e),
        }
        yield {"type": "config_done", "total": 0}
        yield {"type": "_collected", "config": None}
        return

    total = sum(len(v) for v in collected.values())
    yield {"type": "config_done", "total": total}

    yield {
        "type": "_collected",
        "config": TestConfigResponse(
            requirements=collected[REQUIREMENT_LIST_KEY],
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
    test_type: str = "Single-Turn",
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
    resolved_type = TestSetType.from_string(test_type)
    if resolved_type is None:
        resolved_type = TestSetType.SINGLE_TURN
    test_type = resolved_type.value

    config_response: Optional[TestConfigResponse] = config

    if config_response is None:
        # ── Phase 1: Streamed config generation ──

        # Everything needed before the first yield, wrapped together --
        # see stream_error_message's docstring for why this must catch
        # both the LLM resolution and _fetch_db_context (a
        # deleted/inaccessible project also raises here).
        try:
            llm = _resolve_config_llm(db, user)
            db_context = _fetch_db_context(
                db=db,
                organization_id=organization_id,
                prompt=prompt,
                project_id=project_id,
                previous_messages=previous_messages,
            )
        except Exception as e:
            logger.error("Failed to set up config generation: %s", e, exc_info=True)
            yield ndjson({"type": "error", "phase": "config", "message": stream_error_message(e)})
            yield ndjson({"type": "done"})
            return

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

    active_requirements = [b.name for b in config_response.requirements if b.active]
    active_topics = [t.name for t in config_response.topics if t.active]
    active_categories = [c.name for c in config_response.categories if c.active]

    if not active_requirements:
        active_requirements = [b.name for b in config_response.requirements[:1]]

    test_index = 0
    tests_generated = 0

    try:
        if test_type == "Multi-Turn":
            config_dict = {
                "generation_prompt": prompt,
                REQUIREMENT_LIST_KEY: active_requirements,
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
                        "test_type": "Multi-Turn",
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
                requirements=active_requirements,
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
                        "test_type": "Single-Turn",
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
                requirements=active_requirements,
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
                        "test_type": "Single-Turn",
                    }
                )
                test_index += 1
                tests_generated += 1
                await anyio.sleep(0)

    except Exception as e:
        logger.error("Test generation failed at index %d: %s", test_index, e, exc_info=True)
        yield ndjson({"type": "error", "phase": "tests", "message": stream_error_message(e)})

    yield ndjson({"type": "tests_done", "total": tests_generated})
    yield ndjson({"type": "done"})
