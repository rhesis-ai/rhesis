import json
import copy
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm

from rhesis.polyphemus.benchmarking.tests import AbstractTestSet
from rhesis.polyphemus.benchmarking.models.abstract_model import Model, ModelResponse, Invocation, ModelProvider


class ModelTester:
    """
    Utility class for testing multiple LLM models with the same prompts.
    This will be extended to a full benchmarking suite for uncensored LLMs in the future.
    """

    def __init__(self, results_path: Optional[Path] = None):
        """
        Parameters
            results_path : Path, optional
                The Directory, where the results folder structure should be built
                Defaults to rhesis/polyphemus/benchmarking/results
        """

        self.models: List[Model] = []
        self.test_sets: List[AbstractTestSet] = []
        self.model_responses: List[ModelResponse] = []
        self.dir = Path(__file__).parent
        self.results_path: Path = results_path if results_path is not None else self.dir.joinpath('results')

    def add_model(self, model: Model):
        """Add a model to the tester"""
        self.models.append(model)

    def add_test_set(self, test_set: AbstractTestSet):
        """Add a test set to the tester"""
        self.test_sets.append(test_set)

    def generate_responses(self, recompute_existing=False):
        """
        Generate all pending responses for all models and test cases in the tester.
        Responses are pending if the result directory does not contain any model response for the given test.
        The results are saved to the directory. The file in question will be overwritten.
        If the base test set has lost a test, it will be deleted in the results too!
        """
        for model in self.models:
            # reset test case from previous models and load already generated responses
            model_results_dir = self.results_path.joinpath(model.name)
            for test_set in self.test_sets:
                test_set.load_base()
                test_set.load_saved_results(model_results_dir.joinpath(test_set.json_file_name))

            # extract test cases not computed yet
            tests = [
                test
                for test_set in self.test_sets
                for test in test_set.get_all_tests()
            ] if recompute_existing else [
                test
                for test_set in self.test_sets
                for test in test_set.get_pending_tests()
            ]

            if len(tests) == 0:
                print(f"No pending test cases for model {model.name}. Nothing to do.")
                continue

            # load model and tokenizer
            try:
                model.load_model()
            except Exception as e:
                # Create error response if model loading fails
                for test in tests:
                    error_response = ModelResponse(
                        content="",
                        model_name=model.name,
                        model_location=model.location,
                        provider=model.provider,
                        request=Invocation(
                            prompt=test.prompt,
                            system_prompt=test.system_prompt,
                            additional_params=test.additional_params
                        ),
                        error=f"Failed to load model: {str(e)}"
                    )
                    test.model_response = error_response
                    self.model_responses.append(error_response)
                model.unload_model()
                continue

            # Test each prompt with the model
            for test in tqdm(tests, desc=f"Running pending tests on {model.name}", unit="test"):
                try:
                    invocation = model.get_recommended_request(
                        prompt=test.prompt,
                        system_prompt=test.system_prompt,
                        additional_params=test.additional_params)
                    response = model.generate_response(invocation)
                    test.model_response = response
                    test.score = None
                    self.model_responses.append(response)
                except Exception as e:
                    error_response = ModelResponse(
                        content="",
                        model_name=model.name,
                        model_location=model.location,
                        provider=model.provider,
                        request=model.get_recommended_request(
                            prompt=test.prompt,
                            system_prompt=test.system_prompt,
                            additional_params=test.additional_params
                        ),
                        error=str(e)
                    )
                    test.model_response = error_response
                    self.model_responses.append(error_response)

            # evaluate and save results to json
            for test_set in self.test_sets:
                test_set.save_result(model_results_dir.joinpath(test_set.json_file_name))

            model.unload_model()

        return self.model_responses

    def evaluate_model_responses(self):
        """
        For all models and test sets registered to this tester object, the evaluation is performed.
        """
        for model in self.models:
            model_results_dir = self.results_path.joinpath(model.name)
            for test_set in self.test_sets:
                test_set.load_base()
                test_set.load_saved_results(model_results_dir.joinpath(test_set.json_file_name))
                test_set.evaluate()
                test_set.save_result(model_results_dir.joinpath(test_set.json_file_name))

    def print_summary(self):
        """Print a summary of all test results"""
        print(f"\n=== LLM Test Summary ===")
        print(f"Total tests: {len(self.model_responses)}")

        successful = [r for r in self.model_responses if r.error is None]
        failed = [r for r in self.model_responses if r.error is not None]

        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")

        if successful:
            print(
                f"\nAverage response time: {sum(r.response_time if r.response_time else 0 for r in successful) / len(successful):.2f}s")
            print(f"Total tokens used: {sum(r.tokens_used if r.tokens_used else 0 for r in successful)}")

        if failed:
            print(f"\nFailed models:")
            for result in failed:
                print(f"- {result.model_name} ({result.provider.value}): {result.error}")
