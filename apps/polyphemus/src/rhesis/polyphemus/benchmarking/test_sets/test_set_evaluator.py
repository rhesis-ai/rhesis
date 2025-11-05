import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from tqdm import tqdm

from rhesis.sdk.models import BaseLLM

from ..models.judge import Judge
from .utils import (
    Test,
    TestResult,
    read_results_json,
    read_tests_json,
    update_if_result_matches_test,
)

JUDGE = None


class TestSetEvaluator:
    """
    Abstract base class for evaluating test sets.
    Provides a consistent interface for loading tests, adding models, generating responses, and
    evaluating results. Should be inherited by concrete test set classes implementing their own
    evaluation logic.
    """

    def __init__(self, json_path: Path):
        """
        Initialize the test set with a name and JSON file for loading tests.

        Parameters
        ----------
        child__file__ : Path
            Path to the Python file of the child class. Used to resolve the JSON test set file.
        """
        # Initialize paths
        self.base_path: Path = Path(json_path)
        self.results_dir: Path = Path("results", "polyphemus", "benchmarking")
        self.base_file: str = self.base_path.name
        # Unified data structure: list of (Test, [TestResult, ...]) pairs
        self.tests: List[Test] = []
        self.models: List[BaseLLM] = []
        self.results: List[List[TestResult]] = []
        # Load test cases from JSON
        self._load_base()
        self.judge = JUDGE  # Shared judge model for evaluation
        self.max_judging_retries = 5

    def _load_base(self):
        """
        Load the base test set from the base path of the test set.
        Populates self.tests with loaded test cases.
        """
        if self.base_path is None or not self.base_path.exists():
            raise FileNotFoundError("No valid basepath to load. No file to read.")
        tests = read_tests_json(self.base_path)
        if tests is None or len(tests) == 0:
            raise ValueError("No tests found.")
        self.tests = tests

    def load_judge(self):
        """
        Load the shared judge model for evaluation.
        """
        global JUDGE
        if JUDGE is None:
            JUDGE = Judge()
        self.judge = JUDGE
        if self.judge.model is None:
            (self.judge.model, self.judge.tokenizer, self.judge.device) = self.judge.load_model()

    def unload_judge(self):
        """
        Unload the shared judge model to free up resources.
        """
        if self.judge is not None:
            self.judge.unload_model()

    def add_model(self, model: BaseLLM):
        """
        Add a model to the test set. Initializes the result list for the model.

        Parameters
        ----------
        model : BaseLLM
            The model to add.
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
        Load test results from disk and associate them with existing tests.
        Overwrites any existing results for the tests in the test set.

        Parameters
        ----------
        overwrite_existing : bool
            If True, reset and overwrite existing results.
        """
        results = []
        for _, model in enumerate(self.models):
            model_results_dir = self.results_dir.joinpath(model.model_name)
            json_path = model_results_dir.joinpath(f"results_{self.base_file}")
            results.extend(read_results_json(json_path))
        if results is None or len(results) == 0:
            print("WARNING: No results found.")
            return
        # Reset existing result lists
        if overwrite_existing:
            self.results = [[None for _ in range(len(self.tests))] for _ in range(len(self.models))]
        for result in results:
            self._add_result(result)

    def _add_result(self, result: TestResult, overwrite_existing: bool = False):
        """
        Add a test result for a specific test.
        Associates the result with the correct model and test, updating only if appropriate.

        Parameters
        ----------
        result : TestResult
            The test result to add.
        overwrite_existing : bool
            If True, overwrite existing valid results.
        """
        # Find model index or dismiss if model is unknown
        models_names = [model.get_model_name() for model in self.models]
        model_index = models_names.index(result.model_id)

        # Find the test this result belongs to
        for i, test in enumerate(self.tests):
            if update_if_result_matches_test(result, test):
                original_result = self.results[model_index][i]
                if original_result is not None:
                    if original_result.error is None and (
                        result.error is not None or not overwrite_existing
                    ):
                        print(
                            (
                                f"Existing result for model {result.model_id} "
                                f"and test {test.prompt} is valid. Keeping existing result."
                            )
                        )
                        return
                self.results[model_index][i] = result
                return
        print("No matching test found for the provided result. Result not added.")

    def _generate_responses(self, tests: List[Test], model: BaseLLM) -> List[TestResult]:
        """
        Generate responses for a list of tests using the specified model.
        Handles model loading errors and saves results if requested.

        Parameters
        ----------
        tests : List[Test]
            List of tests to run.
        model : BaseLLM
            Model to use for generation.
        save_results : bool
            If True, save results after each test.

        Returns
        -------
        List[TestResult]
            List of generated test results.
        """
        results = []
        if not tests:
            print(f"No pending test cases for model {model.model_name}. Nothing to do.")
            return results
        # load model and tokenizer
        try:
            (model.model, model.tokenizer, model.device) = model.load_model()
        except Exception as e:
            # Create error response if model loading fails
            for test in tests:
                error_result = TestResult(
                    text="",
                    error=f"Failed to load model: {str(e)}",
                    model_id=model.get_model_name(),
                    prompt=test.prompt,
                    system_prompt=test.system_prompt,
                    context=test.context,
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
        for test in tqdm(tests, desc=f"Running pending tests on {model.model_name}", unit="test"):
            response = None
            error = None
            try:
                # Prepare system prompt with context if available
                system_prompt = test.system_prompt
                if test.context:
                    # Prepend context chunks to system prompt
                    context_text = "\n\n".join(test.context)
                    if system_prompt:
                        system_prompt = f"{system_prompt}\n\n# Context Information:\n{context_text}"
                    else:
                        system_prompt = f"# Context Information:\n{context_text}"

                response = model.generate(
                    prompt=test.prompt,
                    system_prompt=system_prompt,
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
                context=test.context,
                # NOTE: the model might have default params that are not listed here
                additional_params=test.additional_params,
                expected_text=test.expected_text,
                score=None,
                details=None,
            )
            self._add_result(test_result, overwrite_existing=True)
            results.append(test_result)
        model.unload_model()
        return results

    def generate_pending_responses(self) -> List[TestResult]:
        """
        Generate responses for all test cases that don't have results yet or have errors.

        Parameters
        ----------
        save_results : bool
            If True, save results after generation.

        Returns
        -------
        List[TestResult]
            List of generated test results.
        """
        results = []
        for model_index, model in enumerate(self.models):
            tests = []
            for test_index, test in enumerate(self.tests):
                existing_result = self.results[model_index][test_index]
                if existing_result is None or existing_result.error is not None:
                    tests.append(test)
            new_results = self._generate_responses(tests, model)
            results.extend(new_results)
            if new_results:
                self.save_results(model_index_to_save=model_index)
        return results

    def generate_all_responses(self) -> List[TestResult]:
        """
        Generate responses for all tests in the test set for all models.

        Parameters
        ----------
        save_results : bool
            If True, save results after generation.

        Returns
        -------
        List[TestResult]
            List of generated test results.
        """
        results = []
        for model_index, model in enumerate(self.models):
            results.extend(self._generate_responses(self.tests, model))
            self.save_results(model_index_to_save=model_index)
        return results

    def _evaluate_test_result(self, test_result: TestResult):
        """
        Evaluate using SDK metrics + Perspective API.

        Metrics: Fluency, Relevancy, Refusal Detection, Context Retention (if context), Toxicity
        """
        from ..metrics import (
            ContextRetentionJudge,
            FluencyJudge,
            PerspectiveToxicity,
            RefusalDetection,
            RelevancyJudge,
        )

        test_result.details = {}
        self.load_judge()

        # Fluency
        fluency = FluencyJudge(model=self.judge)
        try:
            r = fluency.evaluate(
                input=test_result.prompt,
                output=test_result.text,
                expected_output=test_result.expected_text,
            )
            test_result.details["fluency"] = {"score": r.score, **r.details}
        except Exception as e:
            test_result.details["fluency"] = {"error": str(e)}

        # Relevancy
        relevancy = RelevancyJudge(model=self.judge)
        try:
            r = relevancy.evaluate(
                input=test_result.prompt,
                output=test_result.text,
            )
            test_result.details["relevancy"] = {"score": r.score, **r.details}
        except Exception as e:
            test_result.details["relevancy"] = {"error": str(e)}

        # Refusal Detection
        refusal = RefusalDetection(model=self.judge)
        try:
            r = refusal.evaluate(
                input=test_result.prompt,
                output=test_result.text,
            )
            # Store as boolean: True if complied, False if refused
            # Score is categorical: "COMPLIED" or "REFUSED"
            complied = r.score == "COMPLIED"
            test_result.details["refusal"] = {
                "complied": complied,
                "refused": not complied,
                "verdict": r.score,  # "COMPLIED" or "REFUSED"
                "score": 1.0 if complied else 0.0,  # Numeric for averaging
                **r.details,
            }
        except Exception as e:
            test_result.details["refusal"] = {"error": str(e)}

        # Context Retention (if context available)
        if test_result.context:
            context_retention = ContextRetentionJudge(model=self.judge)
            try:
                r = context_retention.evaluate(
                    input=test_result.prompt,
                    output=test_result.text,
                    expected_output=test_result.expected_text,
                    context=test_result.context,
                )
                test_result.details["context_retention"] = {"score": r.score, **r.details}
            except Exception as e:
                test_result.details["context_retention"] = {"error": str(e)}

        # Toxicity (Perspective API)
        try:
            perspective = PerspectiveToxicity()
            test_result.details["toxicity"] = perspective.evaluate(test_result.text)
        except Exception as e:
            test_result.details["toxicity"] = {"error": str(e)}

        # Overall score: average of available metric scores
        # Process all metrics in details automatically
        numeric_scores = []

        for metric_name, metric_data in test_result.details.items():
            if not isinstance(metric_data, dict):
                continue  # Skip non-dict entries

            score = metric_data.get("score")

            if score is not None:
                try:
                    # Try direct conversion to float
                    numeric_scores.append(float(score))
                except (TypeError, ValueError):
                    # For non-numeric scores, check if there's an is_successful field
                    is_successful = metric_data.get("is_successful")
                    if is_successful is not None:
                        # Convert pass/fail to 1.0/0.0
                        numeric_scores.append(1.0 if is_successful else 0.0)
                    # Otherwise skip this metric (can't convert)

        test_result.score = (
            sum(numeric_scores) / len(numeric_scores) if numeric_scores else None
        )

    def evaluate_results(self, recompute_existing: bool = False):
        """
        Run the evaluation logic on all test results.
        Evaluates only results with valid model responses and no errors.

        Parameters
        ----------
        recompute_existing : bool
            If True, recompute scores even for results that already have scores.
        """
        for model_index, model_results in enumerate(self.results):
            for test_result in model_results:
                if test_result.text is None or test_result.error is not None:
                    print("No model response: Can't evaluate this test.")
                    test_result.score = None
                    continue
                if not recompute_existing and test_result.score is not None:
                    continue
                self._evaluate_test_result(test_result)
            self.save_results(model_index_to_save=model_index)

    def _save_results(self, results: List[TestResult], json_path: Path):
        """
        Save the test results to the given path. Overwrites any existing file.

        Parameters
        ----------
        results : List[TestResult]
            List of test results to save.
        json_path : Path
            Path where to save the results.
        """
        if json_path is None:
            return
        try:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, mode="w") as f:
                json.dump(
                    {
                        "results": [asdict(result) for result in results if result is not None],
                    },
                    f,
                    indent=2,
                    default=str,
                )
                print(f"Results saved to file: {json_path.absolute()}")
        except FileNotFoundError:
            print("No valid json_path specified. File is not saved.")
            return

    def save_results(self, model_index_to_save=None):
        """
        Save the test results to the given path. Overwrites any existing file.

        Parameters
        ----------
        model_index_to_save : int, optional
            If specified, only save results for the given model index.
        """
        for model_index, model in enumerate(self.models):
            if model_index_to_save is not None and model_index != model_index_to_save:
                continue
            model_results_dir = self.results_dir.joinpath(model.model_name)
            model_results_dir.mkdir(parents=True, exist_ok=True)
            json_path = model_results_dir.joinpath(f"results_{self.base_file}")
            self._save_results(self.results[model_index], json_path)
