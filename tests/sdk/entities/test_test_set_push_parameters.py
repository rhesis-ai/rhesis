"""A pushed or exported test set keeps each test's parameters."""

from rhesis.sdk.entities import Prompt, Test, TestSet


def _test(**kwargs) -> Test:
    return Test(category="c", requirement="r", topic="t", prompt=Prompt(content="x"), **kwargs)


def test_parameters_are_sent():
    test = _test(test_parameters={"account": "A-17"})

    payload = TestSet(name="Accounts", tests=[test])._test_to_dict(test)

    assert payload["test_parameters"] == {"account": "A-17"}


def test_a_test_without_parameters_sends_none():
    test = _test()

    assert "test_parameters" not in TestSet(name="Plain", tests=[test])._test_to_dict(test)
