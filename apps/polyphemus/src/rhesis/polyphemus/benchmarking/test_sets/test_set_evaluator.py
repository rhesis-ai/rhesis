import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from tqdm import tqdm

from rhesis.sdk.models import BaseLLM

from .utils import (
    Test,
    TestResult,
    read_results_json,
    read_tests_json,
    update_if_result_matches_test,
)


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
        self.results_dir: Path = self.base_path.parent.parent.joinpath("results")
        self.base_file: str = self.base_path.name
        # Unified data structure
        self.tests: List[Test] = []
        self.models: List[BaseLLM] = []
        self.results: List[List[TestResult]] = []
        # Load test cases from JSON
        self._load_base()
        self.judge = None  # Judge model for evaluation (set by tester)

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

    def set_judge(self, judge):
        """
        Set the judge model for evaluation.

        Parameters
        ----------
        judge : Judge
            The judge model to use for evaluation.
        """
        self.judge = judge

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

    def load_results(self):
        """
        Load test results from disk and associate them with existing tests.
        WARNING: Resets existing in-memory results before loading.
        """
        results = []
        for _, model in enumerate(self.models):
            model_results_dir = self.results_dir.joinpath(model.model_name)
            json_path = model_results_dir.joinpath(f"results_{self.base_file}")
            results.extend(read_results_json(json_path))
        if results is None or len(results) == 0:
            print("WARNING: No results found.")
            return
        # Reset existing result lists before loading
        self.results = [[None for _ in range(len(self.tests))] for _ in range(len(self.models))]
        for result in results:
            self._add_result(result)

    def _add_result(self, result: TestResult, overwrite: bool = False):
        """
        Add a test result for a specific test.

        Simple overwrite policy:
        - If overwrite=True: Always replace existing result (even if valid)
        - If overwrite=False: Only add if no existing result (None or has error)

        Parameters
        ----------
        result : TestResult
            The test result to add.
        overwrite : bool
            If True, always overwrite existing results.
            If False, only add if slot is empty (None) or has error.
        """
        # Find model index or dismiss if model is unknown
        models_names = [model.get_model_name() for model in self.models]
        model_index = models_names.index(result.model_id)

        # Find the test this result belongs to
        for i, test in enumerate(self.tests):
            if update_if_result_matches_test(result, test):
                existing = self.results[model_index][i]

                if not overwrite and existing is not None and existing.error is None:
                    # Don't overwrite valid existing result
                    return

                # Overwrite (or add if None)
                self.results[model_index][i] = result
                return

        print(f"Warning: No matching test found for result from {result.model_id}")

    def _generate_responses(self, tests: List[Test], model: BaseLLM) -> List[TestResult]:
        """
        Generate responses for a list of tests using the specified model.
        Handles model loading errors and automatically saves results.
        WARNING: This method will always overwrite existing results for the given tests.

        Parameters
        ----------
        tests : List[Test]
            List of tests to run.
        model : BaseLLM
            Model to use for generation.

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
                    test_metadata=test.test_metadata,
                    metadata=None,
                    score=None,
                    details=None,
                    cost=None,
                )
                self._add_result(error_result, overwrite=True)
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

                # Capture performance metadata from SDK models
                metadata = None
                if hasattr(model, "last_generation_metadata"):
                    metadata = model.last_generation_metadata

            except Exception as e:
                error = str(e)
                metadata = None

            test_result = TestResult(
                model_id=model.get_model_name(),
                text=response,
                metadata=metadata,
                error=error,
                prompt=test.prompt,
                system_prompt=test.system_prompt,
                context=test.context,
                # NOTE: the model might have default params that are not listed here
                additional_params=test.additional_params,
                expected_text=test.expected_text,
                test_metadata=test.test_metadata,
                score=None,
                details=None,
                cost=None,
            )
            self._add_result(test_result, overwrite=True)
            results.append(test_result)
        model.unload_model()
        return results

    def generate_pending_responses(self) -> List[TestResult]:
        """
        Generate responses for all test cases that don't have results yet or have errors.
        Automatically saves results after each model completes.

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
        Automatically saves results after each model completes.

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

    def _calculate_cost_metric(self, test_result: TestResult):
        """
        Calculate efficiency/cost metric from performance metadata.

        The cost metric represents computational complexity using:
        - Generation time (seconds)
        - Model memory (GB)
        - Output tokens

        Formula: cost = (seconds_per_token * model_memory_gb * 1000)

        This gives a dimensionless cost score where:
        - Lower is better (faster, less memory)
        - Typical range: 0.01 - 100+
        - ~0.1 = very efficient (fast, low memory)
        - ~1.0 = moderate (typical small model)
        - ~10+ = expensive (slow or high memory)

        Returns cost value or None if metadata unavailable.
        """
        if not test_result.metadata:
            return None

        metadata = test_result.metadata

        # Extract essential metrics from SDK
        generation_time = metadata.get("generation_time_seconds", 0)
        output_tokens = metadata.get("output_tokens", 0)
        model_memory_gb = metadata.get("model_memory_gb", 0)

        # Handle edge cases
        if generation_time == 0 or output_tokens == 0 or model_memory_gb == 0:
            return None

        # Calculate derived metric
        seconds_per_token = generation_time / output_tokens if output_tokens > 0 else 0

        # Calculate cost metric
        # Formula: time_per_token × model_memory
        cost = seconds_per_token * model_memory_gb

        # Add a small baseline cost for extremely efficient cases
        # This prevents zero costs and accounts for fixed overhead
        baseline_cost = 0.01
        cost = max(cost, baseline_cost)

        return round(cost, 4)

    def _evaluate_test_result(self, test_result: TestResult):
        """
        Evaluate using SDK metrics + Perspective API + Cost metric.

        Metrics: Fluency, Relevancy, Refusal Detection, Context Retention (if context), Toxicity
        Cost: Efficiency metric (separate from quality score)
        """
        from ..metrics import (
            ContextRetentionJudge,
            FluencyJudge,
            PerspectiveToxicity,
            RefusalDetection,
            RelevancyJudge,
        )

        test_result.details = {}

        # Calculate cost metric if metadata available
        test_result.cost = self._calculate_cost_metric(test_result)

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

        for _, metric_data in test_result.details.items():
            if not isinstance(metric_data, dict):
                continue

            score = metric_data.get("score")

            if score is not None:
                try:
                    # Try direct conversion to float
                    numeric_scores.append(float(score))
                except (TypeError, ValueError):
                    # Otherwise skip this metric (can't convert)
                    pass

        test_result.score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else None

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
                # Skip None results (test not run yet)
                if test_result is None:
                    continue

                # Skip results with errors or no response
                if test_result.text is None or test_result.error is not None:
                    print("No model response: Can't evaluate this test.")
                    test_result.score = None
                    continue

                # Skip already evaluated if not recomputing
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
