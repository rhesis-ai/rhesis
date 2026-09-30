"""Prove the built wheels install and work, before they reach PyPI.

#2834 published a wheel with no package code in it, and #2835 borrowed the OTLP
exporter's session. Both looked fine to `python -m build` and only broke once
installed. The SDK test suite runs against `sdk/src`, so it cannot see either.

Run this against the built artifacts in a fresh venv, never the source tree:

    python scripts/sdk_wheel_smoke_test.py path/to/rhesis-*.whl path/to/rhesis_sdk-*.whl
"""

import json
import sys
import zipfile
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import urlparse

# What each distribution has to ship. The rhesis wheel is the runtime the SDK
# imports; the SDK wheel is the code users import by name.
REQUIRED_FILES = {
    "rhesis": ("rhesis/__init__.py", "rhesis/py.typed"),
    "rhesis-sdk": ("rhesis/__init__.py", "rhesis/sdk/__init__.py", "rhesis/py.typed"),
}

# Nothing here may reach the network or a real backend. Port 1 is reserved and
# refuses instantly, so a client built against it fails fast instead of hanging.
DEAD_URL = "http://127.0.0.1:1"


def distribution_of(wheel: Path) -> str:
    """`rhesis_sdk-0.17.1-py3-none-any.whl` -> `rhesis-sdk`."""
    return wheel.name.split("-")[0].replace("_", "-")


def check_wheel_contents(wheel: Path) -> None:
    """Fail if a wheel is missing the files its importers need."""
    name = distribution_of(wheel)
    required = REQUIRED_FILES.get(name)
    if required is None:
        sys.exit(f"Unknown distribution {name!r} in {wheel.name}; add it to REQUIRED_FILES")

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    missing = [path for path in required if path not in names]
    if missing:
        packaged = sum(path.endswith(".py") for path in names)
        sys.exit(f"{wheel.name} is missing {missing} (only {packaged} .py files packaged)")


def check_installed_from(wheel: Path) -> None:
    """Fail if the installed distribution is not the wheel we just built.

    rhesis-sdk depends on `rhesis[telemetry]`, so installing the SDK wheel alone
    would pull the already-published rhesis from PyPI and quietly test that
    instead of the one about to be published.
    """
    name = distribution_of(wheel)
    try:
        provenance = distribution(name).read_text("direct_url.json")
    except PackageNotFoundError:
        sys.exit(f"{name} is not installed; install {wheel.name} before running this")

    if provenance is None:
        sys.exit(
            f"{name} has no direct_url.json, so we cannot tell which wheel was "
            f"installed. Install {wheel.name} by path for this check to mean anything."
        )
    installed_from = Path(urlparse(json.loads(provenance)["url"]).path).name
    if installed_from != wheel.name:
        sys.exit(f"{name} was installed from {installed_from}, not the {wheel.name} we built")


def check_sdk_imports() -> None:
    """Import the SDK and exercise the entry points a first install touches."""
    import rhesis.sdk
    from rhesis.sdk import RhesisClient, endpoint, metric

    if "site-packages" not in rhesis.sdk.__file__:
        sys.exit(f"rhesis.sdk came from {rhesis.sdk.__file__}, not from the installed wheel")

    # project_id is passed explicitly: given only an api_key the client
    # introspects the token over the network, which is not what this measures.
    client = RhesisClient(
        api_key="smoke-test-key",
        base_url=DEAD_URL,
        project_id="smoke-test-project",
    )
    if not isinstance(client, RhesisClient):
        sys.exit(f"RhesisClient() returned {type(client).__name__}")

    @endpoint(name="smoke_endpoint", description="Wheel smoke test")
    def smoke_endpoint(text: str) -> str:
        return text

    # @metric wraps the function, so decorating it is the assertion. The wrapper
    # takes no positional arguments, and the signature must have input and output.
    @metric(name="smoke_metric")
    def smoke_metric(input: str, output: str) -> bool:
        return bool(output)

    if smoke_endpoint("ping") != "ping":
        sys.exit("@endpoint changed the return value")
    if not callable(smoke_metric):
        sys.exit("@metric did not return a callable")

    print(f"imported rhesis-sdk {rhesis.sdk.__version__}, client and decorators work")


def main(argv: list[str]) -> int:
    if not argv:
        sys.exit("usage: sdk_wheel_smoke_test.py <wheel> [<wheel> ...]")

    wheels = [Path(argument) for argument in argv]
    for wheel in wheels:
        if not wheel.is_file():
            sys.exit(f"{wheel} is not a file; build the wheels before running this")

    # Half a check is worse than none: a stale or missing wheel would otherwise
    # leave one distribution unverified and still report success.
    covered = {distribution_of(wheel) for wheel in wheels}
    if covered != set(REQUIRED_FILES):
        sys.exit(f"Expected wheels for {sorted(REQUIRED_FILES)}, got {sorted(covered)}")

    for wheel in wheels:
        check_wheel_contents(wheel)
    print(f"wheels contain their package sources ({len(wheels)} checked)")

    for wheel in wheels:
        check_installed_from(wheel)

    check_sdk_imports()

    # Without this the OTLP batch processor holds the runner open for its
    # shutdown delay, retrying the dead URL the whole time.
    from rhesis.telemetry.provider import shutdown_tracer_provider

    shutdown_tracer_provider()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
