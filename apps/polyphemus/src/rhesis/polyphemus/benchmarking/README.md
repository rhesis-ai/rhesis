# Polyphemus Benchmarking

This module provides a benchmarking suite for evaluating multiple Large Language Models (LLMs) using consistent test sets and prompts. It is designed for extensibility and future expansion.

## Main Components

- **ModelTester**: Utility class for managing models and test sets, generating responses, and evaluating results.
- **Test Sets**: Abstract and concrete implementations for organizing and evaluating test cases. Example: `MockTestSet` in `test_sets/harmless/`.
- **Models**: Model wrappers for specific LLMs (e.g., DeepHermes3, Hermes3, Dolphin3) in `models/`.

## Usage

1. **Add models**: Use `ModelTester.add_model()` to add LLMs.
2. **Add test sets**: Use `ModelTester.add_test_set()` to add test sets.
3. **Generate responses**: Call `ModelTester.generate_responses()` to run models on test sets.
4. **Evaluate responses**: Call `ModelTester.evaluate_model_responses()` to score model outputs.
5. **Print summary**: Use `ModelTester.print_summary()` for a concise result overview.

## Example

```python
from rhesis.polyphemus.benchmarking import ModelTester
from rhesis.polyphemus.benchmarking.models import DeepHermes3, Hermes3, Dolphin3
from rhesis.polyphemus.benchmarking.test_sets.harmless import MockTestSet

tester = ModelTester()
tester.add_model(DeepHermes3())
tester.add_model(Hermes3())
tester.add_model(Dolphin3())
tester.add_test_set(MockTestSet())
tester.generate_responses()
tester.evaluate_model_responses()
tester.print_summary()
```

## Results
The results are organized in the following folder structure:

```
results/
	polyphemus/
		benchmarking/
			NousResearch/
				DeepHermes-3-Llama-3-3B-Preview/
					harmful/
                    harmless/
			dphn/
				Dolphin3.0-Llama3.2-3B/
					harmful/
                    harmless/
```

## Extending
- Add new models in `models/` by subclassing `HuggingFaceLLM`.
- Add new test sets in `test_sets/` by subclassing `AbstractTestSet`.

## Notes
- Do not use or reference any files or code marked/named as `harmfull`.
- See `AMD.md` for GPU installation instructions.
