"""
Configuration for the Rhesis release tool including component definitions.
"""

from pathlib import PurePosixPath


class ComponentConfig:
    """Configuration for a component"""

    def __init__(
        self,
        config_file: str,
        config_type: str,
        changelog_path: str,
        follows_platform: bool = False,
    ):
        self.config_file = config_file
        self.config_type = config_type
        self.changelog_path = changelog_path
        self.follows_platform = follows_platform

    @property
    def path(self) -> str:
        """Directory the component lives in, used to scope `git log` to its own commits.

        Every component keeps its version file at the root of its own directory, so the
        config file's parent is the component root. PurePosixPath because git wants
        forward slashes regardless of platform.
        """
        return str(PurePosixPath(self.config_file).parent)


# Component configurations.
#
# A follows_platform component ships as part of the platform: it takes the platform's version and
# is covered by the platform's `v<version>` tag, so it is never bumped or tagged on its own. It
# stays in here because it still keeps its own changelog, scoped to its own directory.
COMPONENTS = {
    "backend": ComponentConfig(
        "apps/backend/pyproject.toml",
        "pyproject",
        "apps/backend/CHANGELOG.md",
        follows_platform=True,
    ),
    "frontend": ComponentConfig(
        "apps/frontend/package.json",
        "package",
        "apps/frontend/CHANGELOG.md",
        follows_platform=True,
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


def follows_platform(component: str) -> bool:
    """Whether a component takes the platform's version instead of carrying its own"""
    return component in COMPONENTS and COMPONENTS[component].follows_platform


def platform_followers() -> list[str]:
    """Components released as part of the platform, in COMPONENTS order"""
    return [name for name, config in COMPONENTS.items() if config.follows_platform]


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
