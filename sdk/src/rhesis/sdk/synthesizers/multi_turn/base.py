from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM


class GenerationConfig(BaseModel):
    generation_prompt: str
    behavior: Optional[str] = None
    category: Optional[str] = None
    topic: Optional[str] = None


class Prompt(BaseModel):
    goal: str
    instructions: list[str]
    restrictions: list[str]


class Test(BaseModel):
    prompt: Prompt
    behavior: str
    category: str
    topic: str


class Tests(BaseModel):
    tests: List[Test]


class MultiTurnSynthesizer:
    prompt_template_file: str = "base.jinja"

    def __init__(self, config: GenerationConfig, model: Optional[Union[str, BaseLLM]]):
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

    def generate(self, num_tests: int = 5) -> Tests:
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
        test_set = TestSet(tests=response["tests"], metadata=metadata)

        return test_set
