from typing import List

from rhesis.polyphemus.benchmarking.tests.abstract_testset import Test, AbstractTestSet


class MockTestSet(AbstractTestSet):
    def __init__(self, name: str):
        super().__init__(name, "mock_test_set.json")

    def evaluate(self):
        for test_case in self.test_set:
            if test_case.model_response is None or test_case.model_response.error is not None:
                print("No model response: Can't evaluate this test.")
                test_case.score = None
                continue

            if test_case.expected_response in test_case.model_response.content:
                test_case.score = 1.0
            else:
                test_case.score = 0.0