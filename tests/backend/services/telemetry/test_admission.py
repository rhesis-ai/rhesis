"""Trace ingest admission: the queue-depth read."""

from kombu import Connection, Exchange, Queue

from rhesis.backend.app.services.telemetry import admission


def test_queue_depth_counts_messages_in_every_priority_list(monkeypatch):
    """Kombu files a message sent with a priority under a separate Redis list."""
    import redis

    # The test container's Redis, on a database nothing else in the suite uses.
    redis_url = admission._redis_url(14)
    client = redis.Redis.from_url(redis_url)
    client.delete(*admission._QUEUE_KEYS)
    monkeypatch.setattr(admission._redis, "get", lambda db: client)

    queue = Queue(
        admission.INGEST_QUEUE,
        Exchange(admission.INGEST_QUEUE),
        routing_key=admission.INGEST_QUEUE,
    )
    with Connection(redis_url) as connection:
        producer = connection.Producer()
        for priority in (None, 5, 9):
            producer.publish(
                {"probe": priority},
                exchange=queue.exchange,
                routing_key=admission.INGEST_QUEUE,
                declare=[queue],
                priority=priority,
            )

    try:
        assert admission._QueueDepth().get() == 3
    finally:
        client.delete(*admission._QUEUE_KEYS)


def test_settings_refuse_an_inflight_cap_no_gzip_request_fits(monkeypatch):
    import pytest
    from pydantic import ValidationError

    from rhesis.backend.app.config.settings import TraceIngestSettings

    monkeypatch.setenv("TRACE_INGEST_MAX_INFLIGHT_BYTES", str(1024 * 1024))
    with pytest.raises(ValidationError, match="TRACE_INGEST_MAX_INFLIGHT_BYTES"):
        TraceIngestSettings()
