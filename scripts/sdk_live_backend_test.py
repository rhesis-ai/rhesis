"""Run an SDK app against a real backend, the way a user's first app does.

The online counterpart of `sdk_wheel_smoke_test.py`, which never reaches a
backend. Run nightly from a fresh venv with the latest third-party deps, so a
new release of a dependency, or a backend change the SDK has not caught up
with, fails within a day instead of on a user's machine.

It starts a child process that builds `RhesisClient.from_environment()`,
registers an `@endpoint` and an `@metric`, and calls `connect()`. Then it
creates a test set and runs it through the API against that endpoint, scored
only by that metric, and checks every result. No LLM is involved, so the
backend needs no model and no key.

Needs a backend with a worker on the `test-runs` queue and a project-scoped
token, as `tests/docker-compose.test.yml --profile sdk` and the integration
conftest seed give:

    RHESIS_BASE_URL=http://localhost:10003 RHESIS_API_KEY=rh-test-token \\
    RHESIS_PROJECT_ID=12340000-0000-4000-8000-000000001234 \\
        python scripts/sdk_live_backend_test.py
"""

import os
import signal
import subprocess
import sys
import time
import uuid

ENDPOINT_NAME = "nightly_echo"
METRIC_NAME = "nightly_echo_check"
PROMPTS = ("What are your opening hours?", "Do you sell gluten-free bread?")

REGISTER_TIMEOUT = 60
RUN_TIMEOUT = 300
FINAL_STATUSES = {"Completed", "Partial", "Failed"}


def echo(text: str) -> str:
    return f"echo: {text}"


def run_app() -> None:
    """The child process: a minimal app that serves one endpoint and one metric."""
    from rhesis.sdk import RhesisClient, endpoint, metric

    client = RhesisClient.from_environment()
    if not isinstance(client, RhesisClient):
        sys.exit(f"from_environment() returned {type(client).__name__}, not RhesisClient")

    @endpoint(name=ENDPOINT_NAME)
    # The zero-config signature from the @endpoint docs. With `input` alone the backend
    # is not sure enough of its mapping and asks an LLM, which this backend does not have.
    def nightly_echo(input: str, session_id: str | None = None) -> dict:
        return {"output": echo(input), "session_id": session_id}

    @metric(name=METRIC_NAME, score_type="binary")
    def nightly_echo_check(input: str, output: str) -> dict:
        passed = output == echo(input)
        return {"score": 1.0 if passed else 0.0, "details": {"reason": f"got {output!r}"}}

    client.connect()


def wait_for(what: str, check, app: subprocess.Popen, timeout: float):
    """Poll `check` until it returns something truthy, failing if the app dies."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if app.poll() is not None:
            sys.exit(f"the app exited with {app.returncode} while waiting for {what}")
        result = check()
        if result:
            return result
        time.sleep(1)
    sys.exit(f"timed out after {timeout}s waiting for {what}")


def find_by_name(endpoint, name: str) -> dict | None:
    from rhesis.sdk.clients import APIClient, Methods

    found = APIClient().send_request(
        endpoint=endpoint, method=Methods.GET, params={"$filter": f"name eq '{name}'"}
    )
    return found[0] if found else None


def run_status(run_id: str) -> str | None:
    from rhesis.sdk.clients import APIClient, Endpoints, Methods

    run = APIClient().send_request(
        endpoint=Endpoints.TEST_RUNS, method=Methods.GET, url_params=run_id
    )
    status = run.get("status") or {}
    name = status.get("name") if isinstance(status, dict) else status
    return name if name in FINAL_STATUSES else None


def check_results(results: list[dict]) -> None:
    """Every test must have the echoed output and a passing score from our metric."""
    if len(results) != len(PROMPTS):
        sys.exit(f"expected {len(PROMPTS)} test results, got {len(results)}: {results}")

    expected_outputs = {echo(prompt) for prompt in PROMPTS}
    for result in results:
        test_output = result.get("test_output")
        # The backend allows a plain string here too.
        output = test_output.get("output") if isinstance(test_output, dict) else test_output
        if output not in expected_outputs:
            sys.exit(f"the endpoint answer did not come back: test_output={test_output}")

        test_metrics = result.get("test_metrics")
        metrics = test_metrics.get("metrics") if isinstance(test_metrics, dict) else None
        metrics = metrics if isinstance(metrics, dict) else {}
        scored = metrics.get(METRIC_NAME)
        if not scored:
            sys.exit(f"{METRIC_NAME} did not score the result: test_metrics={test_metrics}")
        if scored.get("score") != 1.0 or not scored.get("is_successful"):
            sys.exit(f"{METRIC_NAME} failed: {scored}")
        unexpected = set(metrics) - {METRIC_NAME}
        if unexpected:
            sys.exit(f"the run used metrics it was not given: {sorted(unexpected)}")


def run_test_set() -> None:
    import rhesis.sdk
    from rhesis.sdk.clients import Endpoints as Routes
    from rhesis.sdk.entities import Endpoint, TestRun, TestSet
    from rhesis.sdk.enums import TestType

    print(f"rhesis-sdk {rhesis.sdk.__version__} from {rhesis.sdk.__file__}")
    if "site-packages" not in rhesis.sdk.__file__:
        sys.exit("rhesis.sdk is not an installed package; run this from the fresh venv")

    app = subprocess.Popen([sys.executable, __file__, "--app"])
    try:
        found = wait_for(
            f"endpoint {ENDPOINT_NAME!r}",
            lambda: find_by_name(Routes.ENDPOINTS, ENDPOINT_NAME),
            app,
            REGISTER_TIMEOUT,
        )
        wait_for(
            f"metric {METRIC_NAME!r}",
            lambda: find_by_name(Routes.METRICS, METRIC_NAME),
            app,
            REGISTER_TIMEOUT,
        )
        endpoint = Endpoint.model_validate(found)
        print(f"connected: endpoint {endpoint.id} and metric {METRIC_NAME} registered")

        test_set = TestSet(
            name=f"Nightly SDK run {uuid.uuid4().hex[:8]}",
            description="Nightly SDK run against a live backend",
            short_description="Nightly",
            test_set_type=TestType.SINGLE_TURN,
            tests=[
                {
                    "category": "Nightly",
                    "topic": "Echo",
                    "requirement": "Echo",
                    "prompt": {"content": p},
                }
                for p in PROMPTS
            ],
        )
        test_set.push()

        submitted = test_set.execute(endpoint, metrics=[METRIC_NAME])
        run_id = submitted["test_run_id"]
        print(f"submitted test run {run_id}")

        status = wait_for(
            f"test run {run_id} to finish", lambda: run_status(run_id), app, RUN_TIMEOUT
        )
        results = TestRun(id=run_id).get_test_results()
        if status != "Completed":
            sys.exit(f"test run ended {status}: {results}")
        check_results(results)
        print(f"test run {run_id} completed: {len(results)} results, all scored by {METRIC_NAME}")
    finally:
        app.send_signal(signal.SIGINT)
        try:
            app.wait(timeout=15)
        except subprocess.TimeoutExpired:
            app.kill()


def main() -> int:
    if "--app" in sys.argv[1:]:
        run_app()
        return 0

    missing = [
        v for v in ("RHESIS_BASE_URL", "RHESIS_API_KEY", "RHESIS_PROJECT_ID") if not os.getenv(v)
    ]
    if missing:
        sys.exit(f"set {', '.join(missing)}")
    run_test_set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
