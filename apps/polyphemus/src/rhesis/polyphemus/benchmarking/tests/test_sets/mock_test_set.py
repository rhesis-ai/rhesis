from typing import List

from rhesis.polyphemus.benchmarking.tests.abstract_testset import Test, AbstractTestSet


class MockTestSet(AbstractTestSet):
    """
    This class provides a very minimal test set to showcase Test Sets
    """

    def __init__(self, name: str):
        """
        The super constructor should be called with a name and the path to the JSON of the test set
        Alternatively, no test set will be loaded in super constructor and can be provided here (not recommended).
        """
        super().__init__(name, "mock_test_set.json")

    def evaluate_test(self, test):
        """
        This method should use the model responses of each test to evaluate it and set its score.
        """
        if test.expected_response in test.model_response.content:
            test.score = 1.0
        else:
            test.score = 0.0
