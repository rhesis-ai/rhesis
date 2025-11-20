from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM


class GenerationConfig(BaseModel):
    generation_prompt: str
    behaviors: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    topics: Optional[list[str]] = None


class Prompt(BaseModel):
    goal: str
    instructions: str = ""  # Optional - how Penelope should conduct the test
    restrictions: str = ""  # Optional - forbidden behaviors for the target
    scenario: str = ""  # Optional - contextual framing for the test


class Test(BaseModel):
    prompt: Prompt
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
        metadata = {
            "synthesizer": "MultiTurnSynthesizer",
            "batch_size": 1,
            "generation_prompt": self.config.generation_prompt,
        }
        test_set = TestSet(
            tests=response["tests"], metadata=metadata, test_set_type=TestType.MULTI_TURN.value
        )

        return test_set
