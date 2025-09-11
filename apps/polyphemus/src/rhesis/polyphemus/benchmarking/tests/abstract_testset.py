import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import List

from rhesis.sdk.models import BaseLLM
from tqdm import tqdm

from .utils import (
    Test,
    TestResult,
    read_results_json,
    read_tests_json,
    test_result_matches_test,
)


class AbstractTestSet(ABC):
    """
    This abstract class provides a consistent interface to evaluate test sets.
    It should be inherited by other classes that implement their own evaluation logic
    """

    def __init__(self, json_file_name: str):
        """
        Initialize the test set with a name and json file name for loading tests.

        Args:
            name: The test set name that identifies the specific test set
            json_file_name: The json file name used to load the tests from the test_sets directory
        """
        self.json_file_name = json_file_name
        self.base_path: Path = Path(__file__).parent.joinpath(
            "test_sets", self.json_file_name
        )
        # Unified data structure: list of (Test, [TestResult, ...]) pairs
        self.tests: List[Test] = []
        self.models: List[BaseLLM] = []  # only need the model names
        self.results: List[List[TestResult]] = []
        self._load_base()

    def _load_base(self):
        """
        Load the base test set from the base path of the test set.
        """
        if self.base_path is None or not self.base_path.exists():
            print("No valid basepath to load. No file to read.")
            return

        tests = read_tests_json(self.base_path)

        if tests is None or len(tests) == 0:
            print("WARNING: No tests found.")
            return
        # Initialize unified structure with empty result lists
        self.tests = tests

    def add_model(self, model: BaseLLM):
        """
        Add a model to the test set. This will initialize the result list for the model.

        Args:
            model: The model to add
        """
        # Check if model is already added
        for existing_model in self.models:
            if existing_model.model_name == model.model_name:
                print(f"Model {model.model_name} is already added to the test set.")
                return

        self.models.append(model)
        self.results.append([None for _ in range(len(self.tests))])

    def load_results(self, overwrite_existing: bool = True):
        """
        Load test results from the given path and associate them with existing tests.
        This will overwrite any existing results for the tests in the test set.

        Args:
            json_path: Path to the JSON file containing test results
        """
        results = []
        for _, model in enumerate(self.models):
            model_results_dir = Path(__file__).parent.joinpath(
                "results", model.model_name
            )
            json_path = model_results_dir.joinpath(f"results_{self.json_file_name}")
            results.extend(read_results_json(json_path))

        if results is None or len(results) == 0:
            print("WARNING: No results found.")
            return

        # Reset existing result lists
        if overwrite_existing:
            self.results = [
                [None for _ in range(len(self.tests))] for _ in range(len(self.models))
            ]

        for result in results:
            self._add_result(result)

    def _add_result(self, result: TestResult, overwrite_existing: bool = False):
        """
        Add a test result for a specific test.

        Args:
            test: The test this result belongs to
            result: The test result to add
        """
        # Find model index or dismiss if model is unknown
        model_index = -1
        for i, model in enumerate(self.models):
            if model.get_model_name() == result.model_id:
                model_index = i
                break

        if model_index == -1:
            print(f"Unknown model: {result.model_id}. Result not added.")
            return

        # Find the test this result belongs to
        for i, test in enumerate(self.tests):
            if test_result_matches_test(result, test):
                original_result = self.results[model_index][i]
                if original_result is not None:
                    if original_result.error is None and (
                        result.error is not None or not overwrite_existing
                    ):
                        print(
                            f"Existing result for model {result.model_name} and test {test.prompt} is valid. Keeping existing result."
                        )
                        return
                self.results[model_index][i] = result
                return

        print("No matching test found for the provided result. Result not added.")

    def _generate_responses(
        self, tests: List[Test], model: BaseLLM
    ) -> List[TestResult]:
        results = []

        if len(tests) == 0:
            print(f"No pending test cases for model {model.model_name}. Nothing to do.")
            return results

        # load model and tokenizer
        try:
            model.load_model()
        except Exception as e:
            # Create error response if model loading fails
            for test in tests:
                error_result = TestResult(
                    text="",
                    error=f"Failed to load model: {str(e)}",
                    model_id=model.get_model_name(),
                    prompt=test.prompt,
                    system_prompt=test.system_prompt,
                    additional_params=test.additional_params,
                    expected_text=test.expected_text,
                    metadata=None,
                    score=None,
                    details=None,
                )
                self._add_result(error_result)
                results.append(error_result)
            print(f"Failed to load model {model.model_name}. Error: {str(e)}")
            return results

        # Test each prompt with the model
        for test in tqdm(
            tests, desc=f"Running pending tests on {model.model_name}", unit="test"
        ):
            response = None
            error = None

            try:
                response = model.generate(
                    prompt=test.prompt,
                    system_prompt=test.system_prompt,
                    **test.additional_params,
                )
            except Exception as e:
                error = str(e)

            test_result = TestResult(
                model_id=model.get_model_name(),
                text=response,
                metadata=None,
                error=error,
                prompt=test.prompt,
                system_prompt=test.system_prompt,
                # NOTE: the model might have default params that are not listed here
                additional_params=test.additional_params,
                expected_text=test.expected_text,
                score=None,
                details=None,
            )
            self._add_result(test_result, overwrite_existing=True)
            results.append(test_result)
        return results

    def generate_pending_responses(self) -> List[TestResult]:
        """
        Return a list of all test cases that don't have any results yet.

        Returns:
            List of tests that need to be executed
        """
        results = []

        for model_index, model in enumerate(self.models):
            tests = []
            for test_index, test in enumerate(self.tests):
                existing_result = self.results[model_index][test_index]
                if existing_result is None or existing_result.error is not None:
                    tests.append(test)
            results.extend(self._generate_responses(tests, model))

        return results

    def generate_all_responses(self) -> List[TestResult]:
        """
        Return all tests in the test set.

        Returns:
            List of all tests
        """
        results = []

        for model in self.models:
            results.extend(self._generate_responses(self.tests, model))

        return results

    @abstractmethod
    def _evaluate_test_result(self, test_result: TestResult):
        """
        Evaluate a single test result and set its score.

        This method should use the model response to evaluate the test result
        and set its score. Each test set will have its own evaluation logic.

        Args:
            test_result: The test result to evaluate
        """
        pass

    def evaluate_results(self, recompute_existing: bool = False):
        """
        Run the evaluation logic on all test results.

        Args:
            recompute_existing: If True, recompute scores even for results that already have scores
        """
        for model_results in self.results:
            for test_result in model_results:
                if test_result.text is None or test_result.error is not None:
                    print("No model response: Can't evaluate this test.")
                    test_result.score = None
                    continue
                if not recompute_existing and test_result.score is not None:
                    continue
                self._evaluate_test_result(test_result)

    def _safe_results(self, results: List[TestResult], json_path: Path):
        """
        Save the test results to the given path. This will overwrite any existing file!

        Args:
            results: List of test results to save
            json_path: Path where to save the results
        """
        if json_path is None:
            return

        try:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, mode="w") as f:
                json.dump(
                    {
                        "results": [asdict(result) for result in results],
                    },
                    f,
                    indent=2,
                    default=str,
                )
                print(f"Results saved to file: {json_path.absolute()}")
        except FileNotFoundError:
            print("No valid json_path specified. File is not saved.")
            return

    def save_results(self):
        """
        Save the test results to the given path. This will overwrite any existing file!

        Args:
            json_path: Path where to save the results
        """
        for model_index, model in enumerate(self.models):
            model_results_dir = Path(__file__).parent.joinpath(
                "results", model.model_name
            )
            model_results_dir.mkdir(parents=True, exist_ok=True)
            self._safe_results(
                self.results[model_index],
                model_results_dir.joinpath(f"results_{self.json_file_name}"),
            )
