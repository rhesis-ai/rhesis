import os

from rhesis.polyphemus.benchmarking.tests.abstract_testset import (
    AbstractTestSet,
    TestResult,
)


class MockTestSet(AbstractTestSet):
    """
    This class provides a very minimal test set to showcase Test Sets
    """

    def __init__(self):
        """
        The super constructor should be called with a name and the path to the JSON of the test set
        Alternatively, no test set will be loaded in super constructor and can be provided here (not recommended).
        """

        super().__init__(os.path.basename(__file__).replace(".py", ".json"))

    def _evaluate_test_result(self, test_result: TestResult):
        """
        This method should use the model responses of each test to evaluate it and set its score.
        """
        if test_result.expected_text in test_result.text:
            test_result.score = 1.0
        else:
            test_result.score = 0.0
