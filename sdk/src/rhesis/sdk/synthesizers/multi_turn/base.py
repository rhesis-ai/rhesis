from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel

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


class TestConfiguration(BaseModel):
    goal: str
    instructions: str = ""  # Optional - how Penelope should conduct the test
    restrictions: str = ""  # Optional - forbidden behaviors for the target
    scenario: str = ""  # Optional - contextual framing for the test


class Test(BaseModel):
    test_configuration: TestConfiguration
    behavior: str
    category: str
    topic: str
    test_type: str = TestType.MULTI_TURN.value


class Tests(BaseModel):
    tests: List[Test]


class MultiTurnSynthesizer:
    prompt_template_file: str = "base.jinja"

    def __init__(self, config: GenerationConfig, model: Optional[Union[str, BaseLLM]] = None):
        self.config = config

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

    def generate(self, num_tests: int = 5) -> TestSet:
        prompt_template = self.load_prompt_template(self.prompt_template_file)
        template_context = {
            "num_tests": num_tests,
            **self.config.model_dump(),
        }
        prompt = prompt_template.render(template_context)
        response = self.model.generate(prompt, schema=Tests)

        # Convert tests to dict format
        # Multi-turn tests use test_configuration (not prompt field)
        multi_turn_tests = []
        for test in response["tests"]:
            test_dict = test if isinstance(test, dict) else test.model_dump()

            # Ensure test_configuration is a dict (not a Pydantic model)
            if "test_configuration" in test_dict and isinstance(
                test_dict["test_configuration"], BaseModel
            ):
                test_dict["test_configuration"] = test_dict["test_configuration"].model_dump()

            multi_turn_tests.append(test_dict)

        # Use utility function to create TestSet with proper name/description
        test_set = create_test_set(
            tests=multi_turn_tests,
            model=self.model,
            synthesizer_name="MultiTurnSynthesizer",
            batch_size=1,
            num_tests=len(multi_turn_tests),
            requested_tests=num_tests,
            generation_prompt=self.config.generation_prompt,
        )

        # Set test_set_type for multi-turn tests
        test_set.test_set_type = TestType.MULTI_TURN.value

        # Add "(Multi-Turn)" suffix to the name
        if test_set.name:
            test_set.name = f"{test_set.name} (Multi-Turn)"

        return test_set
