from pathlib import Path
from typing import List, Optional, Union

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

    def _generate_batch(self) -> List[dict]:
        """Generate a single batch of tests."""
        prompt_template = self.load_prompt_template(self.prompt_template_file)
        template_context = {
            "num_tests": self.batch_size,
            **self.config.model_dump(),
        }
        prompt = prompt_template.render(template_context)
        response = self.model.generate(prompt, schema=Tests)

        batch_tests = []
        for test in response["tests"]:
            test_dict = test if isinstance(test, dict) else test.model_dump()

            if "test_configuration" in test_dict and isinstance(
                test_dict["test_configuration"], BaseModel
            ):
                test_dict["test_configuration"] = test_dict["test_configuration"].model_dump()

            test_dict["test_type"] = TestType.MULTI_TURN.value
            batch_tests.append(test_dict)

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
