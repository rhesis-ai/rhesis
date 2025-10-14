# Benchmarking Polyphemus
To select model(s) for test generation, we need to benchmark multiple options and decide on one.
To make this selection both reproducible and extendable, we set out to create a modular benchmarking suite.
The benchmarking contains 3 main components:
1. Models
2. Test Sets
3. Tester

The following sections explain how those work and how to use them.

## Models
There is an Abstract Class `Model` functioning as an interface to unify the usage of all models.
All Models are Child objects of this class and therefore have the following important attributes:

| attribute | function                                                                                                         |
|-----------|------------------------------------------------------------------------------------------------------------------|
| name      | A nickname used for in different places. The filenames of the test results depend on it, so it should be unique. |
| provider  | Where is the model hosted / downloadable (e.g. Huggingface, Google).                                             |
| location  | What is the location of the model at the used provider. e.g. `meta-llama/Meta-Llama-3-8B`.                       |

After creating a Model, you can access the following methods

| method                  | function                                                                                                                                                |
|-------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| load_model              | Load the model from the source location (e.g. Huggingface) and make the other functions available.                                                      |
| generate_response       | Given an `Invocation` object, generate a `ModelResponse` object where the model answers the prompt.                                                     |
| get recommended_request | Gives an `Invocation` object, containing all the standards for the model. If you already have passed the same parameter, it will overwrite the default. |
| unload_model            | Unloads the model itself and frees the associated memory.                                                                                               |

To include support for a new model, you should Inherit from the `Model` Class
or find a more specific option to inherit from (e.g. `HuggingfaceModel`)

You can create a new instance of a model by running
```
from rhesis.polyphemus.benchmarking.models import MockModel
model = MockModel(name='Mock Model', location='None')
```

To find more models, look in the models directory, as this is under current development.

## Test Sets
As with the Model, there is an Abstract Class `AbstractTestSet` provided as an interface.
A Test Set is defined as a set of tests, that has the same evaluation logic.

All Models are Child objects of this class and therefore have the following important attributes:

| attribute      | function                                                                                                                   |
|----------------|----------------------------------------------------------------------------------------------------------------------------|
| name           | A nickname used to identify the Test Set (warning if not matching on import from json).                                    |
| base_path      | The directory of the original tests (without the model responses) for this Test Set.                                       |
| json_file_name | Dictates the filename for both loading the Test Set and storing the results (at least as it is implemented in the tester). |

Each Test Set holds the Tests as well as the responses and scores to them (both stored in the `Test` object).
Therefore, when testing a new model on the same TestSet
the results have to be reset by loading the base state (automatically handled by the tester).

For this and other functionality a Test Set provides the following functions:

| method             | function                                                                                                          |
|--------------------|-------------------------------------------------------------------------------------------------------------------|
| evaluate_test      | This method should be implemented by each specific Test Set. It contains the scoring logic for each response.     |
| evaluate           | Calls evaluate_test safely for each test in the Test Set.                                                         |
| load_base          | Loads the base state of the Test Set from the base JSON.                                                          |
| load_saved_results | Loads the results of a previous run given its JSON Path. Keeps only the Tests also contained in the base version. |
| get_pending_tests  | Returns the Tests, that don't have a valid response yet.                                                          |
| get_all_tests      | Returns all Tests contained in the Test Set.                                                                      |

For the `evaluate` function to work as expected, each specific Test Set has to implement the `evaluate_test` method.
This method will then be called on each Test

## Tester
The Model Tester is a wrapper for all the complexity described before.
You can simply create a `ModelTester` object (providing a custom results path if needed) and add all Models and Test Sets to it.
The built-in functions will do the rest for you:

| method                   | function                                                                                                                               |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| add_model                | Adds an object inheriting from the `Model` class to the list of models to test.                                                        |
| add_test_set             | Adds an object inheriting from the `AbstractTestSet` class to the list of tests to run for the models.                                 |
| generate_responses       | Generates responses of all models for all the Tests. Already computed Tests will not be recomputed unless `recompute_existing` is set. |
| evaluate_model_responses | Evaluates all TestSets for all models added to the ModelTester skipping scores already present unless `recompute_existing` is set.     |
| print_summary            | prints a small summary of how many Tests completed and how many had ann error while running.                                           |
