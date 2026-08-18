import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel, Field

from rhesis.sdk.entities.test import TestConfiguration
from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.utils import create_test_set, stamp_multi_turn

logger = logging.getLogger(__name__)

# A batch failing this many times in a row (bad/error LLM response) gives up
# on that batch rather than retrying forever.
_MAX_BATCH_RETRIES = 3


class GenerationConfig(BaseModel):
    generation_prompt: str
    requirements: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    additional_context: Optional[str] = None


class Test(BaseModel):
    test_configuration: TestConfiguration
    requirement: str
    category: str
    topic: str
    # Note: test_type is NOT included in the schema sent to the LLM
    # It will be added programmatically after generation


class Tests(BaseModel):
    tests: List[Test]


# Flat schema for LLM batch generation (easier for the model to produce).
# Repacked to nested Test structure after generation.
class FlatTest(BaseModel):
    test_configuration_goal: str
    test_configuration_instructions: str
    test_configuration_restrictions: str
    test_configuration_scenario: str
    test_configuration_min_turns: int = Field(ge=1, le=50)
    test_configuration_max_turns: int = Field(ge=1, le=50)
    requirement: str
    category: str
    topic: str


class FlatTests(BaseModel):
    tests: List[FlatTest]


class MultiTurnSynthesizer:
    prompt_template_file: str = "base.jinja"

    def __init__(
        self,
        config: GenerationConfig,
        model: Optional[Union[str, BaseLLM]] = None,
        batch_size: int = 10,
        harmful: bool = False,
    ):
        self.config = config
        self.batch_size = batch_size
        self.harmful = harmful
        self.last_error: Optional[str] = None

        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

    def load_prompt_template(self, prompt_template_file: str) -> "Template":
        """Load prompt template from assets or use custom prompt."""
        templates_path = Path(__file__).parent / "templates"
        environment = Environment(loader=FileSystemLoader(templates_path))
        template = environment.get_template(prompt_template_file)
        return template

    def _flat_test_to_nested(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        """Repack a flat test dict (LLM output) into the nested Test structure."""
        config: Dict[str, Any] = {
            "goal": flat["test_configuration_goal"],
            "instructions": flat["test_configuration_instructions"],
            "restrictions": flat["test_configuration_restrictions"],
            "scenario": flat["test_configuration_scenario"],
        }
        min_turns = flat.get("test_configuration_min_turns")
        max_turns = flat.get("test_configuration_max_turns")
        if min_turns is not None:
            config["min_turns"] = int(min_turns)
        if max_turns is not None:
            config["max_turns"] = int(max_turns)
        return {
            "test_configuration": config,
            "requirement": flat["requirement"],
            "category": flat["category"],
            "topic": flat["topic"],
        }

    def _generate_batch(self) -> List[dict]:
        """Generate a single batch of tests.

        Returns an empty list (rather than raising) when the model's
        response doesn't contain usable tests, so a single flaky call --
        e.g. Polyphemus responding with ``{"error": ...}`` while still
        scaling up from zero -- can be retried by the caller instead of
        crashing the whole generation run with a raw ``KeyError``.
        """
        prompt_template = self.load_prompt_template(self.prompt_template_file)
        template_context = {
            "num_tests": self.batch_size,
            "harmful": self.harmful,
            **self.config.model_dump(),
        }
        prompt = prompt_template.render(template_context)

        # Use flat schema for LLM (easier to generate), then repack to nested
        response = self.model.generate(prompt, schema=FlatTests)

        if isinstance(response, dict) and "error" in response:
            self.last_error = str(response["error"])
            logger.error("[MultiTurnSynthesizer] LLM returned error: %s", self.last_error)
            return []

        if not isinstance(response, dict) or "tests" not in response:
            self.last_error = f"Unexpected response type: {type(response).__name__}"
            logger.error(
                "[MultiTurnSynthesizer] Unexpected response type=%s: %s",
                type(response).__name__,
                str(response)[:500],
            )
            return []

        flat_tests = response["tests"]

        batch_tests = [
            {
                **self._flat_test_to_nested(flat),
                "test_type": TestType.MULTI_TURN.value,
            }
            for flat in flat_tests
        ]

        return batch_tests

    async def generate_stream(self, num_tests: int = 5) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield multi-turn test dicts one-by-one as they parse from the LLM."""
        from rhesis.sdk.synthesizers.streaming import IncrementalJsonArrayParser

        prompt_template = self.load_prompt_template(self.prompt_template_file)
        template_context = {
            "num_tests": num_tests,
            "harmful": self.harmful,
            **self.config.model_dump(),
        }
        prompt = prompt_template.render(template_context)
        parser = IncrementalJsonArrayParser()

        token_stream = self.model.generate_stream(prompt=prompt, schema=FlatTests)
        async for chunk in token_stream:
            for flat in parser.feed(chunk):
                yield {
                    **self._flat_test_to_nested(flat),
                    "test_type": TestType.MULTI_TURN.value,
                }

    def generate(self, num_tests: int = 5) -> TestSet:
        num_batches = num_tests // self.batch_size

        if num_batches == 0:
            num_batches = 1
            self.batch_size = num_tests

        all_tests = []
        for batch_index in range(num_batches):
            for attempt in range(1, _MAX_BATCH_RETRIES + 1):
                batch_tests = self._generate_batch()
                if batch_tests:
                    break
                logger.warning(
                    "[MultiTurnSynthesizer] Batch %d/%d attempt %d/%d produced no "
                    "tests (%s), retrying",
                    batch_index + 1,
                    num_batches,
                    attempt,
                    _MAX_BATCH_RETRIES,
                    self.last_error,
                )
            all_tests.extend(batch_tests)

        if not all_tests:
            reason = f": {self.last_error}" if self.last_error else ""
            raise ValueError(f"Failed to generate any valid test cases{reason}")

        test_set = create_test_set(
            tests=all_tests,
            model=self.model,
            synthesizer_name="MultiTurnSynthesizer",
            batch_size=self.batch_size,
            num_tests=len(all_tests),
            requested_tests=num_tests,
            generation_prompt=self.config.generation_prompt,
        )

        return stamp_multi_turn(test_set)
