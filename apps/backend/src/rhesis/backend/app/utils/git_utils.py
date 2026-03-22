"""
Utility functions for getting git information.
"""

import os
import subprocess
from typing import Optional, Tuple


def get_git_info() -> Tuple[Optional[str], Optional[str]]:
    """
    Get the current git branch and commit hash.
    Checks CI-injected env vars first (GIT_BRANCH, GIT_COMMIT), then falls back
    to running git commands (for local development).

    Returns:
        Tuple of (branch_name, commit_hash) or (None, None) if git info unavailable
    """
    branch = os.getenv("GIT_BRANCH")
    commit = os.getenv("GIT_COMMIT")
    if branch or commit:
        return branch, commit

    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        commit_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        )
        commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None

        return branch, commit

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None, None


def should_show_git_info() -> bool:
    """
    Determine if git information should be shown based on environment.
    Returns True for non-production environments.
    """
    backend_env = os.getenv("BACKEND_ENV", "").lower()
    environment = os.getenv("ENVIRONMENT", "").lower()

    # Don't show git info in production
    return backend_env != "production" and environment != "production"


def get_version_info() -> dict:
    """
    Get version information including git details when appropriate.

    Returns:
        Dictionary with version information
    """
    from rhesis.backend import __version__

    version_info = {"version": __version__}

    if should_show_git_info():
        branch, commit = get_git_info()
        if branch:
            version_info["branch"] = branch
        if commit:
            version_info["commit"] = commit

    return version_info
