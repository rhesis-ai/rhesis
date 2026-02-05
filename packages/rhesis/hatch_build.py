"""Custom hatch build hook to inject dynamic versions into dependencies."""

import re
from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface


class DynamicDependenciesHook(MetadataHookInterface):
    """Hatch metadata hook that sets dependencies with versions from each package."""

    PLUGIN_NAME = "dynamic-deps"

    # Map package names to their pyproject.toml locations (relative to repo root)
    PACKAGE_PATHS = {
        "rhesis-sdk": "sdk/pyproject.toml",
        "rhesis-penelope": "penelope/pyproject.toml",
    }

    def update(self, metadata: dict) -> None:
        """Set dependencies with dynamic versions from each package's pyproject.toml."""
        repo_root = Path(self.root) / ".." / ".."

        # Load versions for each package
        sdk_version = self._get_version_from_pyproject(repo_root / self.PACKAGE_PATHS["rhesis-sdk"])
        penelope_version = self._get_version_from_pyproject(
            repo_root / self.PACKAGE_PATHS["rhesis-penelope"]
        )

        # Set main dependencies
        metadata["dependencies"] = [
            f"rhesis-sdk>={sdk_version}",
        ]

        # Set optional dependencies
        metadata["optional-dependencies"] = {
            # Multi-turn testing agent
            "penelope": [f"rhesis-penelope>={penelope_version}"],
            # SDK optional extras (pass-through)
            "huggingface": [f"rhesis-sdk[huggingface]>={sdk_version}"],
            "garak": [f"rhesis-sdk[garak]>={sdk_version}"],
            "langchain": [f"rhesis-sdk[langchain]>={sdk_version}"],
            "langgraph": [f"rhesis-sdk[langgraph]>={sdk_version}"],
            "autogen": [f"rhesis-sdk[autogen]>={sdk_version}"],
            # Bundle options
            "all-integrations": [
                f"rhesis-sdk[all-integrations]>={sdk_version}",
                f"rhesis-penelope>={penelope_version}",
            ],
            "all": [
                f"rhesis-sdk[all]>={sdk_version}",
                f"rhesis-penelope>={penelope_version}",
            ],
        }

    def _get_version_from_pyproject(self, pyproject_path: Path) -> str:
        """Extract version from a pyproject.toml file."""
        content = pyproject_path.read_text()
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1)
        raise ValueError(f"Could not find version in {pyproject_path}")
