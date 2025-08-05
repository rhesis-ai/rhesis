from typing import List

from rhesis.polyphemus.benchmarking.tests.abstract_testset import TestCase, AbstractTestSet


class MockTestSet(AbstractTestSet):
    def __init__(self, name: str):
        super().__init__(name)
        self.test_set: List[TestCase] = [
            TestCase(
                prompt="What is your name?",
                system_prompt="Your name is Felix!",
                expectation="Felix"
            ),
            TestCase(
                prompt="What is your age?",
                system_prompt="Your age is 70 Billion! You are really old",
                expectation="70 Billion"
            ),
            TestCase(
                prompt="What is your gender?",
                system_prompt="Your gender is Male!",
                expectation="Male"
            )
        ]

    def evaluate(self):
        for test_case in self.test_set:
            if test_case.model_response is None or test_case.model_response.error is not None:
                print("No model response: Can't evaluate this test.")
                test_case.score = None
                continue

            if test_case.expectation in test_case.model_response.content:
                test_case.score = 1.0
            else:
                test_case.score = 0.0