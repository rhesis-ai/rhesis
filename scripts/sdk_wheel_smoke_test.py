"""Prove the built wheels install and work, before they reach PyPI.

#2834 published a wheel with no package code in it, and #2835 borrowed the OTLP
exporter's session. Both looked fine to `python -m build` and only broke once
installed. The SDK test suite runs against `sdk/src`, so it cannot see either.

Each profile runs in its own fresh venv, against the same built wheels:

- The `core` profile installs `rhesis-sdk` and checks that what connecting an
  app needs works, that `[all]` features raise the install hint, and that no
  `[all]` package came along.
- The `all` profile installs `rhesis-sdk[all]` and checks that every `[all]`
  feature imports.

An undeclared core dependency (jsonschema) or an unbounded `[all]` one (mcp 2
breaking `rhesis.sdk.agents`) only shows up in a fresh resolve like this.

    python scripts/sdk_wheel_smoke_test.py --profile core|all \\
        path/to/rhesis-*.whl path/to/rhesis_sdk-*.whl
"""

import argparse
import json
import re
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

# What every missing-feature error must tell the user. Copied from
# rhesis.sdk._extras on purpose: importing it would make the check always pass.
INSTALL_HINT = 'pip install "rhesis-sdk[all]"'
INSTALL_DOCS_URL = "https://docs.rhesis.ai/sdk/installation#what-to-install"

# Neither tier may pull torch; only the huggingface and garak extras do.
NEVER_INSTALLED = ("torch",)


def distribution_of(wheel: Path) -> str:
    """`rhesis_sdk-0.17.1-py3-none-any.whl` -> `rhesis-sdk`."""
    return wheel.name.split("-")[0].replace("_", "-")


def is_installed(name: str) -> bool:
    try:
        distribution(name)
    except PackageNotFoundError:
        return False
    return True


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


def all_extra_packages() -> list[str]:
    """The packages the installed SDK declares for `[all]`, read from its metadata."""
    packages = []
    for requirement in distribution("rhesis-sdk").requires or []:
        spec, _, marker = requirement.partition(";")
        if re.search(r"""extra\s*==\s*["']all["']""", marker):
            packages.append(re.match(r"[A-Za-z0-9._-]+", spec.strip()).group(0))
    if not packages:
        sys.exit("rhesis-sdk declares no [all] extra, so the profile checks mean nothing")
    return packages


def check_installed_packages(profile: str) -> None:
    """Core must have none of the `[all]` packages, `[all]` must have every one."""
    extra = all_extra_packages()
    if profile == "core":
        # Strict on purpose: even a transitive [all] package means the core grew.
        unexpected = [name for name in extra if is_installed(name)]
        if unexpected:
            sys.exit(f"core install pulled [all] packages: {unexpected}")
    else:
        absent = [name for name in extra if not is_installed(name)]
        if absent:
            sys.exit(f"[all] install is missing {absent}")

    heavy = [name for name in NEVER_INSTALLED if is_installed(name)]
    if heavy:
        sys.exit(f"{profile} install pulled {heavy}")
    found = "none" if profile == "core" else "all"
    print(f"{profile}: {found} of the {len(extra)} [all] packages installed, no torch")


def check_sdk_imports() -> None:
    """Import the SDK and exercise the entry points a first install touches."""
    import rhesis.sdk
    from rhesis.sdk import RhesisClient, endpoint, metric, observe

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

    @observe(name="smoke_observe")
    def smoke_observe(text: str) -> str:
        return text

    if smoke_endpoint("ping") != "ping":
        sys.exit("@endpoint changed the return value")
    if smoke_observe("ping") != "ping":
        sys.exit("@observe changed the return value")
    if not callable(smoke_metric):
        sys.exit("@metric did not return a callable")

    version = rhesis.sdk.__version__
    print(f"imported rhesis-sdk {version}, client, @endpoint, @observe and @metric work")


def check_core_features() -> None:
    """What connecting an app needs, on the core install alone."""
    from rhesis.sdk.connector import ConnectorManager  # noqa: F401
    from rhesis.sdk.entities import Endpoints, TestRun, TestRuns, TestSets  # noqa: F401
    from rhesis.sdk.metrics import NumericJudge
    from rhesis.sdk.models import get_model
    from rhesis.sdk.synthesizers import PromptSynthesizer

    # The Rhesis-hosted model is the one core ships with; it builds offline.
    model = get_model("rhesis", api_key="smoke-test-key", base_url=DEAD_URL)
    NumericJudge(evaluation_prompt="Is the output polite?", model=model)
    PromptSynthesizer(prompt="Questions about a bakery", model=model)
    print("core: connector, entities, native judge and synthesizer work")


def expect_full_sdk_error(feature: str, attempt) -> None:
    """Fail unless `attempt` raises the one install hint for `[all]`."""
    from rhesis.sdk._extras import FullSDKRequiredError

    try:
        attempt()
    except FullSDKRequiredError as exc:
        message = str(exc)
        for needle in (INSTALL_HINT, INSTALL_DOCS_URL):
            if needle not in message:
                sys.exit(f"{feature} raised FullSDKRequiredError without {needle!r}: {message}")
        return
    except Exception as exc:
        sys.exit(f"{feature} raised {type(exc).__name__} instead of FullSDKRequiredError: {exc}")
    sys.exit(f"{feature} worked on the core install; it should need rhesis-sdk[all]")


def check_core_guards() -> None:
    """Every kind of guarded entry point gives the same hint on core."""

    def deepeval_metric():
        from rhesis.sdk.metrics import DeepEvalAnswerRelevancy  # noqa: F401

    def agents():
        import rhesis.sdk.agents  # noqa: F401

    def extractor():
        from rhesis.sdk.services import DocumentExtractor  # noqa: F401

    def litellm_model():
        from rhesis.sdk.models import get_model

        get_model("openai/gpt-4o-mini", api_key="smoke-test-key")

    guards = {
        "DeepEvalAnswerRelevancy": deepeval_metric,
        "rhesis.sdk.agents": agents,
        "DocumentExtractor": extractor,
        "get_model('openai/...')": litellm_model,
    }
    for feature, attempt in guards.items():
        expect_full_sdk_error(feature, attempt)
    print(f"core: {len(guards)} [all] features raise the install hint")


def check_all_features() -> None:
    """Every `[all]` feature imports, and the offline ones construct."""
    import rhesis.sdk.agents  # noqa: F401
    from rhesis.sdk.metrics import DeepEvalAnswerRelevancy, DeepTeamSafety  # noqa: F401
    from rhesis.sdk.models import get_model
    from rhesis.sdk.models.providers.litellm import LiteLLM
    from rhesis.sdk.services import DocumentExtractor
    from rhesis.sdk.services.chunker import ChunkingService, IdentityChunker
    from rhesis.sdk.services.extractor import ExtractedSource, SourceType

    DocumentExtractor()

    # IdentityChunker skips tiktoken, which downloads its encodings on first use.
    source = ExtractedSource(type=SourceType.TEXT, name="smoke", content="ping")
    chunks = ChunkingService([source], IdentityChunker()).chunk()
    if [chunk.content for chunk in chunks] != ["ping"]:
        sys.exit(f"chunking returned {chunks!r}")

    model = get_model("openai/gpt-4o-mini", api_key="smoke-test-key")
    if not isinstance(model, LiteLLM):
        sys.exit(f"get_model('openai/gpt-4o-mini') returned {type(model).__name__}")
    print("all: agents, extractor, chunker, DeepEval, DeepTeam and litellm models work")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", choices=("core", "all"), required=True)
    parser.add_argument("wheels", nargs="+", type=Path)
    args = parser.parse_args(argv)

    for wheel in args.wheels:
        if not wheel.is_file():
            sys.exit(f"{wheel} is not a file; build the wheels before running this")

    # Half a check is worse than none: a stale or missing wheel would otherwise
    # leave one distribution unverified and still report success.
    covered = {distribution_of(wheel) for wheel in args.wheels}
    if covered != set(REQUIRED_FILES):
        sys.exit(f"Expected wheels for {sorted(REQUIRED_FILES)}, got {sorted(covered)}")

    for wheel in args.wheels:
        check_wheel_contents(wheel)
    print(f"wheels contain their package sources ({len(args.wheels)} checked)")

    for wheel in args.wheels:
        check_installed_from(wheel)

    check_installed_packages(args.profile)
    check_sdk_imports()
    if args.profile == "core":
        check_core_features()
        check_core_guards()
    else:
        check_all_features()

    # Without this the OTLP batch processor holds the runner open for its
    # shutdown delay, retrying the dead URL the whole time.
    from rhesis.telemetry.provider import shutdown_tracer_provider

    shutdown_tracer_provider()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
