import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Any

from rhesis.polyphemus.benchmarking.models.abstract_model import ModelResponse


@dataclass
class TestCase:
    prompt: str
    system_prompt: Optional[str] = None
    expectation: Optional[str] = None
    model_response: Optional[ModelResponse] = None
    score: Optional[float] = None # from 0 to 1
    additional_params: dict[str, Any] = field(default_factory=dict)


class AbstractTestSet(ABC):
    def __init__(self, name: str):
        self.name = name
        self.json_path: Optional[Path] = Path("./sdk/src/rhesis/sdk/model_scoring/tests/test_sets/mock_test_set.json")
        self.test_set: List[TestCase] = []

        self.from_json()

    @abstractmethod
    def evaluate(self):
        pass

    def to_json(self, json_path: Optional[Path] = None):
        if json_path is not None:
            self.json_path = json_path
        if self.json_path is None:
            print("No json_path specified. File is not saved.")
            return

        try:
            self.json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.json_path, mode='w') as f:
                json.dump({
                    'name': self.name,
                    'test_set': [asdict(test_case) for test_case in self.test_set],
                    'json_path': self.json_path,
                }, f, indent=2, default=str)
                print(f"saved to file: {self.json_path.absolute()}")
        except FileNotFoundError:
            print("No valid json_path specified. File is not saved.")
            return

    def from_json(self, json_path: Optional[Path] = None):
        if json_path is not None:
            self.json_path = json_path
        if self.json_path is None or not self.json_path.exists():
            print("No json_path specified. No file to read.")
            return

        try:
            with open(self.json_path, mode='r') as f:
                json_data = json.load(f)
                self.name = json_data['name']
                self.test_set = [TestCase(**test_case) for test_case in json_data['test_set']]
                self.json_path = Path(json_data['json_path'])
        except FileNotFoundError:
            print("No json_path specified. No file to read.")
            return
        except json.decoder.JSONDecodeError:
            print("Invalid json_path specified. File could not be read.")

    def get_pending_cases(self) -> List[TestCase]:
        pending_cases: List[TestCase] = []

        for test_case in self.test_set:
            if test_case.model_response is None\
                    or test_case.model_response.error is not None: pending_cases.append(test_case)

        return pending_cases
