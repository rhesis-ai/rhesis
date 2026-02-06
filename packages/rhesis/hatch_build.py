"""Custom hatch build hook to pin rhesis to the exact SDK version."""

import re
from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface


class DynamicDependenciesHook(MetadataHookInterface):
    """Hatch metadata hook that pins rhesis to the exact rhesis-sdk version."""

    PLUGIN_NAME = "dynamic-deps"

    def update(self, metadata: dict) -> None:
        """Set dependency on rhesis-sdk with exact version match."""
        repo_root = Path(self.root) / ".." / ".."
        sdk_pyproject = repo_root / "sdk" / "pyproject.toml"

        # Read SDK version
        content = sdk_pyproject.read_text()
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if not match:
            raise ValueError(f"Could not find version in {sdk_pyproject}")

        sdk_version = match.group(1)

        # Pin to exact SDK version - installing rhesis is equivalent to installing rhesis-sdk
        metadata["dependencies"] = [
            f"rhesis-sdk=={sdk_version}",
        ]
