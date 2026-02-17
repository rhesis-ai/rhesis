from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel

from rhesis.sdk.entities.test import TestConfiguration
from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.utils import create_test_set


class GenerationConfig(BaseModel):
    generation_prompt: str
    behaviors: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    additional_context: Optional[str] = None


class Test(BaseModel):
    test_configuration: TestConfiguration
    behavior: str
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
    behavior: str
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
    ):
        self.config = config
        self.batch_size = batch_size

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
        return {
            "test_configuration": {
                "goal": flat["test_configuration_goal"],
                "instructions": flat["test_configuration_instructions"],
                "restrictions": flat["test_configuration_restrictions"],
                "scenario": flat["test_configuration_scenario"],
            },
            "behavior": flat["behavior"],
            "category": flat["category"],
            "topic": flat["topic"],
        }

    def _generate_batch(self) -> List[dict]:
        """Generate a single batch of tests."""
        prompt_template = self.load_prompt_template(self.prompt_template_file)
        template_context = {
            "num_tests": self.batch_size,
            **self.config.model_dump(),
        }
        prompt = prompt_template.render(template_context)

        # Use flat schema for LLM (easier to generate), then repack to nested
        response = self.model.generate(prompt, schema=FlatTests)
        flat_tests = response["tests"]

        batch_tests = [
            {
                **self._flat_test_to_nested(flat),
                "test_type": TestType.MULTI_TURN.value,
            }
            for flat in flat_tests
        ]

        return batch_tests

    def generate(self, num_tests: int = 5) -> TestSet:
        num_batches = num_tests // self.batch_size

        if num_batches == 0:
            num_batches = 1
            self.batch_size = num_tests

        all_tests = []
        for _ in range(num_batches):
            all_tests.extend(self._generate_batch())

        test_set = create_test_set(
            tests=all_tests,
            model=self.model,
            synthesizer_name="MultiTurnSynthesizer",
            batch_size=self.batch_size,
            num_tests=len(all_tests),
            requested_tests=num_tests,
            generation_prompt=self.config.generation_prompt,
        )

        test_set.test_set_type = TestType.MULTI_TURN

        if test_set.name:
            test_set.name = f"{test_set.name} (Multi-Turn)"

        return test_set
