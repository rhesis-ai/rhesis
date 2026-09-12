"""``GET /ready`` -- the probe Kubernetes routes traffic by.

``/health`` deliberately touches no database: it answers the liveness probe, and
a database outage must not look like a dead process and get the pod restarted.
``/ready`` is the other half. It runs one ``SELECT 1`` and returns 503 when the
database does not answer, so the pod leaves the Service until it can serve
again -- without restarting, and without a slow database blocking the event
loop while it decides.
"""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from rhesis.backend.app import main
from rhesis.backend.app.main import READINESS_TIMEOUT_SECONDS, app


@pytest.fixture
def probe_client() -> TestClient:
    """A bare client: the probe is unauthenticated and opens its own connection."""
    return TestClient(app)


@pytest.mark.unit
class TestReadinessProbe:
    def test_ready_when_the_database_answers(self, probe_client, monkeypatch):
        monkeypatch.setattr(main, "_ping_database", lambda: None)

        response = probe_client.get("/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}

    def test_still_ready_while_the_outage_is_inside_the_grace_window(
        self, probe_client, monkeypatch
    ):
        """One failed ping keeps the pod in the Service.

        Every replica shares one database, so failing on the first error would
        take the whole fleet out at once and ingress would answer 503 for
        everything, including routes that touch no database.
        """

        def boom():
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        monkeypatch.setattr(main, "_ping_database", boom)
        monkeypatch.setattr(main, "_last_db_contact", time.monotonic())

        response = probe_client.get("/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "degraded", "database": "slow"}

    def test_unavailable_once_contact_is_older_than_the_grace_window(
        self, probe_client, monkeypatch
    ):
        """A pod with no contact at all for the whole window leaves the Service.

        That is the case rescheduling actually fixes: this pod's pool is wedged
        while its siblings are serving.
        """

        def boom():
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        monkeypatch.setattr(main, "_ping_database", boom)
        monkeypatch.setattr(
            main, "_last_db_contact", time.monotonic() - main.READINESS_GRACE_SECONDS - 1
        )

        response = probe_client.get("/ready")

        assert response.status_code == 503
        assert response.json() == {"status": "unavailable", "database": "unreachable"}

    def test_a_success_refreshes_the_grace_window(self, probe_client, monkeypatch):
        """A recovered database must clear the countdown, not merely pause it."""
        monkeypatch.setattr(
            main, "_last_db_contact", time.monotonic() - main.READINESS_GRACE_SECONDS - 1
        )
        monkeypatch.setattr(main, "_ping_database", lambda: None)

        assert probe_client.get("/ready").status_code == 200
        assert time.monotonic() - main._last_db_contact < 1

    def test_unavailable_when_the_database_hangs(self, probe_client, monkeypatch):
        """A hung connection must not hold the probe open past the timeout.

        psycopg2's own connect_timeout is 10s, five times the probe's budget, so
        the wait_for is what keeps a wedged database from turning every probe
        into a slow 200-or-nothing.
        """
        monkeypatch.setattr(main, "_ping_database", lambda: time.sleep(30))
        monkeypatch.setattr(
            main, "_last_db_contact", time.monotonic() - main.READINESS_GRACE_SECONDS - 1
        )

        started = time.monotonic()
        response = probe_client.get("/ready")
        elapsed = time.monotonic() - started

        assert response.status_code == 503
        assert elapsed < READINESS_TIMEOUT_SECONDS + 3

    def test_timeout_is_short_enough_to_be_a_probe(self):
        assert 0 < READINESS_TIMEOUT_SECONDS <= 5

    def test_health_stays_free_of_the_database(self, probe_client, monkeypatch):
        """Liveness must keep answering while the database is down."""

        def boom():
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        monkeypatch.setattr(main, "_ping_database", boom)

        assert probe_client.get("/health").status_code == 200

    @pytest.mark.asyncio
    async def test_ping_runs_off_the_event_loop(self, monkeypatch):
        """The SELECT runs in a worker thread, not on the loop.

        A blocking probe would be self-defeating: the pod is marked unready
        because its own health check froze everything else in the process.
        """
        import threading

        loop_thread = threading.get_ident()
        seen: list[int] = []

        monkeypatch.setattr(main, "_ping_database", lambda: seen.append(threading.get_ident()))

        await main.readiness_check()

        assert seen and seen[0] != loop_thread

    def test_timeout_reports_unavailable_rather_than_erroring(self, monkeypatch):
        """``asyncio.TimeoutError`` is caught, not surfaced as a 500."""

        async def never(*args, **kwargs):
            await asyncio.sleep(60)

        monkeypatch.setattr(main.anyio.to_thread, "run_sync", never)
        monkeypatch.setattr(
            main, "_last_db_contact", time.monotonic() - main.READINESS_GRACE_SECONDS - 1
        )

        response = asyncio.run(main.readiness_check())

        assert response.status_code == 503
