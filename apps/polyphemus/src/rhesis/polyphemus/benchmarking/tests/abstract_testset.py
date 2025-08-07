import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Any

from rhesis.polyphemus.benchmarking.models.abstract_model import ModelResponse, Invocation, ModelProvider


@dataclass
class Test:
    prompt: str
    system_prompt: Optional[str] = None
    expected_response: Optional[str] = None
    model_response: Optional[ModelResponse] = None
    score: Optional[float] = None  # from 0 to 1
    additional_params: dict[str, Any] = field(default_factory=dict)

    # custom equality method
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Test):
            return False
        if self.prompt != other.prompt:
            return False
        if self.system_prompt != other.system_prompt:
            return False
        if self.expected_response != other.expected_response:
            return False
        for key, value in self.additional_params.items():
            if value != other.additional_params[key]:
                return False

        return True


def read_json(json_path):
    """
    Helper method to extract the needed information for a test set from a json file
    """
    name = None
    test_set = []

    if json_path is None:
        return None, None
    try:
        with open(json_path, mode='r') as f:
            json_data = json.load(f)
            name = json_data['name']

            test_set = []
            for test in json_data['test_set']:
                if 'model_response' in test:
                    model_response_dict = test['model_response']
                    model_response_dict['provider'] = ModelProvider[model_response_dict['provider'].split('.')[-1]]
                    model_response_dict['request'] = Invocation(**model_response_dict['request'])
                    test['model_response'] = ModelResponse(**model_response_dict)

                test_set.append(Test(**test))

    except FileNotFoundError:
        return None, None
    except json.decoder.JSONDecodeError:
        print("Invalid JSON format. File could not be read.")

    return name, test_set


class AbstractTestSet(ABC):
    """
    This abstract class provides a consistent interface to evaluate test sets.
    It should be inherited by other classes that implement their own evaluation logic
    """

    def __init__(self, name: str, json_file_name: str):
        """
        The test set name identifies the specific test set. The json_file_name will be used to load the tests.
        """
        self.name = name
        self.dir = Path(__file__).parent
        self.json_file_name = json_file_name
        self.base_path: Optional[Path] = self.dir.joinpath("test_sets", self.json_file_name)

        self.test_set: List[Test] = []
        self.load_base()

    @abstractmethod
    def evaluate_test(self, test: Test):
        """
        This method should use the model responses of each test to evaluate it and set its score.
        Each test set will have its own evaluation logic.
        """
        pass

    def evaluate(self):
        """
        Runs the evaluation logic on all responses to the tests
        """
        for test in self.test_set:
            if test.model_response is None or test.model_response.error is not None:
                print("No model response: Can't evaluate this test.")
                test.score = None
                continue

            self.evaluate_test(test)

    def save_result(self, json_path):
        """
        saves the results to the given path. This will overwrite any existing results!
        """
        if json_path is None:
            return

        try:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, mode='w') as f:
                json.dump({
                    'name': self.name,
                    'test_set': [asdict(test) for test in self.test_set],
                }, f, indent=2, default=str)
                print(f"Test Set saved to file: {json_path.absolute()}")
        except FileNotFoundError:
            print("No valid json_path specified. File is not saved.")
            return

    def load_json(self, json_path: Path):
        """
        Loads the test set from the given path
        """
        name, test_set = read_json(json_path)
        if name != self.name:
            print("WARNING: Name of loaded json does not match test-set name.")

        if test_set is None or len(test_set) == 0:
            print("WARNING: No test-set found.")
            return

        self.test_set = test_set

    def load_base(self):
        """
        Loads the base test set from the base path of the test set.
        """
        if self.base_path is None or not self.base_path.exists():
            print("No valid basepath to load. No file to read.")
            return

        self.load_json(self.base_path)

    def load_saved_results(self, json_path: Path):
        """
        Loads previously saved results from path and merges the existing (base) test set with the loaded results.
        If a base test set is present, only tests present in the base test set will be used.
        If no base test set is present, all loaded test sets will be used.
        """
        if json_path is None:
            print("No json_path specified. File can't be loaded.")
            return

        if len(self.test_set) == 0:
            print(
                "WARNING: No base test set available. Relying only on saved results. "
                "They may be outdated and can hinder reproducibility"
            )
            self.load_json(json_path)
            return

        name, test_set = read_json(json_path)

        if test_set is None or len(test_set) == 0:
            return

        if name != self.name:
            print("WARNING: Name of loaded json does not match test-set name.")

        for test in test_set:
            for self_test in self.test_set:
                if self_test == test:
                    self_test.model_response = test.model_response
                    self_test.score = test.score

    def get_pending_tests(self) -> List[Test]:
        """
        Returns a list of all test cases not having a model response.
        """
        pending_cases: List[Test] = []

        for test_case in self.test_set:
            if test_case.model_response is None \
                    or test_case.model_response.error is not None: pending_cases.append(test_case)

        return pending_cases

    def get_all_tests(self) -> List[Test]:
        return self.test_set
