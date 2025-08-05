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

    def __init__(self):
        self.models: List[Model] = []
        self.test_sets: List[AbstractTestSet] = []
        self.test_results: List[ModelResponse] = []
        self.model_test_sets_map: dict[Model, List[AbstractTestSet]] = {}
        self.results_path: Path = Path('results')

    def add_model(self, model: Model):
        """Add a model to the tester"""
        self.models.append(model)
        self.model_test_sets_map[model] = copy.deepcopy(self.test_sets)

    def add_test_set(self, test_set: AbstractTestSet):
        """Add a test set to the tester"""
        self.test_sets.append(test_set)
        for model in self.models:
            self.model_test_sets_map[model].append(copy.deepcopy(test_set))

    def generate_pending_responses(self):
        for model in self.models:
            pending_cases = [
                test_case
                for test_set in self.model_test_sets_map[model]
                for test_case in test_set.get_pending_cases()
            ]
            if len(pending_cases) == 0:
                print(f"No pending test cases for model {model.name}. Nothing to do.")
                continue

            # load model and tokenizer
            try:
                model.load_model()
            except Exception as e:
                # Create error response if model loading fails
                for test_set in self.test_sets:
                    for test_case in test_set.get_pending_cases():
                        error_response = ModelResponse(
                            content="",
                            model_name=model.name,
                            model_location=model.location,
                            provider=model.provider,
                            request=Invocation(
                                prompt=test_case.prompt,
                                system_prompt=test_case.system_prompt,
                                additional_params=test_case.additional_params
                            ),
                            error=f"Failed to load model: {str(e)}"
                        )
                        test_case.model_response = error_response
                        self.test_results.append(error_response)
                model.unload_model()
                continue

            # Test each prompt with the model
            for test_case in tqdm(pending_cases, desc=f"Running pending test_cases on {model.name}", unit="case"):
                try:
                    invocation = model.get_recommended_request(
                        prompt=test_case.prompt,
                        system_prompt=test_case.system_prompt,
                        additional_params=test_case.additional_params)
                    response = model.generate_response(invocation)
                    test_case.model_response = response
                    self.test_results.append(response)
                except Exception as e:
                    error_response = ModelResponse(
                        content="",
                        model_name=model.name,
                        model_location=model.location,
                        provider=model.provider,
                        request=model.get_recommended_request(
                            prompt=test_case.prompt,
                            system_prompt=test_case.system_prompt,
                            additional_params=test_case.additional_params
                        ),
                        error=str(e)
                    )
                    test_case.model_response = error_response
                    self.test_results.append(error_response)

            model.unload_model()

        return self.test_results

    def evaluate_test_sets(self):
        self.generate_pending_responses()
        for model in self.models:
            result_directory = self.results_path.joinpath(model.name)
            for test_set in self.model_test_sets_map[model]:
                test_set.evaluate()
                test_set.to_json(result_directory.joinpath(test_set.name + '.json'))

    def test_all_models(self, prompts: list[str] | str, system_prompts: Optional[list[str] | str], **kwargs) -> List[
        ModelResponse]:
        """
        Test all registered models with the same prompt and system-prompt.
        The test results will be stored in the test_results attribute.
        Each call of this function will append the results to the existing test_results.
        To clear the results, use the clear_results() method.
        
        Args:
            prompts: The input prompt to test
            system_prompts: The system prompts to use it for all models.
            It Can be a single string or a list of strings for each prompt.
            Some models may prepend their own system prompt!
            **kwargs: Additional parameters for ModelRequest
            
        Returns:
            List of ModelResponse objects from all models for all prompts
        """
        # ensure a consistent format for prompts and system_prompts
        if not isinstance(prompts, list):
            prompts = [prompts]

        if not isinstance(system_prompts, list):
            system_prompts = [system_prompts] * len(prompts)

        if len(prompts) != len(system_prompts):
            raise ValueError("system_prompt must be a list of the same length as prompt or a single string.")

        responses = []

        for model in self.models:
            # load model and tokenizer
            try:
                model.load_model()
            except Exception as e:
                # Create error response if model loading fails
                for prompt, system_prompt in zip(prompts, system_prompts):
                    error_response = ModelResponse(
                        content="",
                        model_name=model.name,
                        model_location=model.location,
                        provider=model.provider,
                        request=Invocation(prompt=prompt, system_prompt=system_prompt, additional_params=kwargs),
                        error=f"Failed to load model: {str(e)}"
                    )
                    responses.append(error_response)
                    self.test_results.append(error_response)
                model.unload_model()
                continue

            # Test each prompt with the model
            for prompt, system_prompt in zip(prompts, system_prompts):
                try:
                    invocation = model.get_recommended_request(prompt, system_prompt, kwargs)
                    response = model.generate_response(invocation)

                    responses.append(response)
                    self.test_results.append(response)
                except Exception as e:
                    # Create error response if generation fails
                    error_response = ModelResponse(
                        content="",
                        model_name=model.name,
                        model_location=model.location,
                        provider=model.provider,
                        request=Invocation(prompt=prompt, system_prompt=system_prompt, additional_params=kwargs),
                        error=str(e)
                    )

                    responses.append(error_response)
                    self.test_results.append(error_response)
                finally:
                    model.unload_model()

        return responses

    def clear_results(self):
        """Reset the test results"""
        self.test_results = []

    def save_to_file(self, filename: str = "llm_test_results.json"):
        """Export test results to JSON file"""
        with open(filename, 'w') as f:
            json.dump([asdict(result) for result in self.test_results], f, indent=2, default=str)

    def test_results_from_json(self, filename: str = "llm_test_results.json") -> List[ModelResponse]:
        """Load test results from JSON file and return as list of ModelResponse"""
        try:
            with open(filename, 'r') as f:
                raw_data = json.load(f)
                for data in raw_data:
                    # Convert ModelProvider string to enum
                    data['provider'] = ModelProvider[data['provider'].split('.')[-1]]
                self.test_results = [ModelResponse(**data) for data in raw_data]
                return self.test_results
        except FileNotFoundError:
            print(f"File {filename} not found. No results loaded.")
            return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {filename}: {e}")
            return []

    def load_from_file(self, filename: str = "llm_test_results.json"):
        """Load test results from JSON file. This will overwrite the existing results."""
        self.test_results = self.test_results_from_json(filename)

    def append_from_file(self, filename: str = "llm_test_results.json"):
        """Append test results from JSON file to existing results"""
        self.test_results.extend(self.test_results_from_json(filename))

    def print_results(self):
        """Print all test results"""
        for result in self.test_results:
            print(result)
            print("-" * 40)

    def print_summary(self):
        """Print a summary of all test results"""
        print(f"\n=== LLM Test Summary ===")
        print(f"Total tests: {len(self.test_results)}")

        successful = [r for r in self.test_results if r.error is None]
        failed = [r for r in self.test_results if r.error is not None]

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
