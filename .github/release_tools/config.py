"""
Configuration for the Rhesis release tool including component definitions.
"""


class ComponentConfig:
    """Configuration for a component"""
    def __init__(self, config_file: str, config_type: str, changelog_path: str):
        self.config_file = config_file
        self.config_type = config_type
        self.changelog_path = changelog_path


# Component configurations
COMPONENTS = {
    "backend": ComponentConfig(
        "apps/backend/pyproject.toml", "pyproject", "apps/backend/CHANGELOG.md"
    ),
    "frontend": ComponentConfig(
        "apps/frontend/package.json", "package", "apps/frontend/CHANGELOG.md"
    ),
    "worker": ComponentConfig(
        "apps/worker/requirements.txt", "requirements", "apps/worker/CHANGELOG.md"
    ),
    "chatbot": ComponentConfig(
        "apps/chatbot/requirements.txt", "requirements", "apps/chatbot/CHANGELOG.md"
    ),
    "polyphemus": ComponentConfig(
        "apps/polyphemus/pyproject.toml", "pyproject", "apps/polyphemus/CHANGELOG.md"
    ),
    "sdk": ComponentConfig(
        "sdk/pyproject.toml", "pyproject", "sdk/CHANGELOG.md"
    ),
}

# Platform-specific files
PLATFORM_VERSION_FILE = "VERSION"
PLATFORM_CHANGELOG = "CHANGELOG.md"

# Component paths for git operations
COMPONENT_PATHS = {
    "backend": "apps/backend",
    "frontend": "apps/frontend", 
    "worker": "apps/worker",
    "chatbot": "apps/chatbot",
    "polyphemus": "apps/polyphemus",
    "sdk": "sdk",
    "platform": "."
}


def format_component_name(component: str) -> str:
    """Format component name with proper capitalization"""
    if component.lower() == "sdk":
        return "SDK"
    return component.title() 