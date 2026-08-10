"""
Configuration for the Rhesis release tool including component definitions.
"""

from pathlib import PurePosixPath


class ComponentConfig:
    """Configuration for a component"""

    def __init__(self, config_file: str, config_type: str, changelog_path: str):
        self.config_file = config_file
        self.config_type = config_type
        self.changelog_path = changelog_path

    @property
    def path(self) -> str:
        """Directory the component lives in, used to scope `git log` to its own commits.

        Every component keeps its version file at the root of its own directory, so the
        config file's parent is the component root. PurePosixPath because git wants
        forward slashes regardless of platform.
        """
        return str(PurePosixPath(self.config_file).parent)


# Component configurations
COMPONENTS = {
    "backend": ComponentConfig(
        "apps/backend/pyproject.toml", "pyproject", "apps/backend/CHANGELOG.md"
    ),
    "frontend": ComponentConfig(
        "apps/frontend/package.json", "package", "apps/frontend/CHANGELOG.md"
    ),
    "worker": ComponentConfig(
        "apps/worker/pyproject.toml", "pyproject", "apps/worker/CHANGELOG.md"
    ),
    "chatbot": ComponentConfig(
        "apps/chatbot/requirements.txt", "requirements", "apps/chatbot/CHANGELOG.md"
    ),
    "polyphemus": ComponentConfig(
        "apps/polyphemus/pyproject.toml", "pyproject", "apps/polyphemus/CHANGELOG.md"
    ),
    "sdk": ComponentConfig("sdk/pyproject.toml", "pyproject", "sdk/CHANGELOG.md"),
    "ee-backend": ComponentConfig(
        "ee/backend/pyproject.toml", "pyproject", "ee/backend/CHANGELOG.md"
    ),
}

# Platform-specific files
PLATFORM_VERSION_FILE = "VERSION"
PLATFORM_CHANGELOG = "CHANGELOG.md"


def get_component_path(component: str) -> str:
    """Directory to scope git operations to; the platform spans the whole repository"""
    if component in COMPONENTS:
        return COMPONENTS[component].path
    return "."


def format_component_name(component: str) -> str:
    """Format component name with proper capitalization"""
    if component.lower() == "sdk":
        return "SDK"
    return component.title()
