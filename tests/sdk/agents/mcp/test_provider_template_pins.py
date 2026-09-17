"""Every stdio provider fetches its MCP server from a public registry at launch, so an
unpinned spec would run whatever the publisher shipped most recently."""

import json
import re
from pathlib import Path

import pytest

from rhesis.sdk.agents.mcp import client as mcp_client

TEMPLATE_DIR = Path(mcp_client.__file__).parent / "provider_templates"

# Flags and template placeholders that sit alongside the package spec in "args".
NON_PACKAGE_ARGS = {"-y", "--authentication", "pat"}

PINNED_SPEC = re.compile(r"^(?:@[^@/]+/)?[^@/]+@\d+\.\d+\.\d+$")


def _stdio_templates():
    for path in sorted(TEMPLATE_DIR.glob("*.json.j2")):
        raw = path.read_text()
        if '"transport": "stdio"' in raw:
            yield pytest.param(path, id=path.name.removesuffix(".json.j2"))


@pytest.mark.parametrize("template_path", _stdio_templates())
def test_stdio_provider_pins_an_exact_server_version(template_path: Path):
    # Placeholders render to null, which is enough to read the static "args".
    rendered = re.sub(r"\{\{.*?\}\}", "null", template_path.read_text())
    server = next(iter(json.loads(rendered)["mcpServers"].values()))

    specs = [arg for arg in server["args"] if isinstance(arg, str) and arg not in NON_PACKAGE_ARGS]
    assert specs, f"{template_path.name} declares no package to run"
    for spec in specs:
        assert PINNED_SPEC.match(spec), (
            f"{template_path.name} runs '{spec}' unpinned; "
            "use '<package>@<exact version>' so the launched server is reproducible"
        )
