"""Model-token accruals are summed per org and resource, then queued once per flush."""

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services import usage_coalescer


@pytest.fixture
def queued(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "rhesis.backend.jobs.usage.accrue_usage.delay", lambda *args: calls.append(args)
    )
    usage_coalescer.flush()
    calls.clear()
    return calls


@pytest.fixture
def summing(monkeypatch):
    # Long enough that the background flusher never fires during a test.
    monkeypatch.setenv("USAGE_ACCRUAL_FLUSH_SECONDS", "3600")


def test_calls_for_one_org_are_queued_as_one_accrual(queued, summing):
    for amount in (100, 250, 50):
        usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, amount)

    assert queued == []
    usage_coalescer.flush()

    assert queued == [("org-a", QuotaResource.MODEL_TOKENS.value, 400)]


def test_orgs_are_never_summed_together(queued, summing):
    usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, 10)
    usage_coalescer.add("org-b", QuotaResource.MODEL_TOKENS, 20)

    usage_coalescer.flush()

    assert sorted(queued) == [
        ("org-a", QuotaResource.MODEL_TOKENS.value, 10),
        ("org-b", QuotaResource.MODEL_TOKENS.value, 20),
    ]


def test_a_flush_empties_the_sum(queued, summing):
    usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, 10)
    usage_coalescer.flush()
    usage_coalescer.flush()

    assert len(queued) == 1


def test_zero_interval_queues_each_call_at_once(queued, monkeypatch):
    monkeypatch.setenv("USAGE_ACCRUAL_FLUSH_SECONDS", "0")

    usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, 10)

    assert queued == [("org-a", QuotaResource.MODEL_TOKENS.value, 10)]


def test_a_forked_child_does_not_send_the_parents_sum(queued, summing):
    import os

    usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, 100)
    read, write = os.pipe()
    pid = os.fork()
    if pid == 0:  # child: report what it would send, then exit without cleanup
        usage_coalescer.flush()
        os.write(write, str(len(queued)).encode())
        os._exit(0)
    os.waitpid(pid, 0)
    child_sent = int(os.read(read, 16))

    usage_coalescer.flush()

    assert child_sent == 0
    assert queued == [("org-a", QuotaResource.MODEL_TOKENS.value, 100)]


def test_a_bad_interval_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("USAGE_ACCRUAL_FLUSH_SECONDS", "two seconds")

    assert usage_coalescer.flush_seconds() == 2.0


def test_a_sum_that_failed_to_queue_is_sent_with_the_next_flush(monkeypatch, summing):
    sent = []

    def broker_down_once(*args):
        if not sent:
            sent.append(None)
            raise ConnectionError("broker down")
        sent.append(args)

    monkeypatch.setattr("rhesis.backend.jobs.usage.accrue_usage.delay", broker_down_once)
    usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, 100)
    usage_coalescer.flush()
    usage_coalescer.add("org-a", QuotaResource.MODEL_TOKENS, 5)
    usage_coalescer.flush()

    assert sent[1:] == [("org-a", QuotaResource.MODEL_TOKENS.value, 105)]
