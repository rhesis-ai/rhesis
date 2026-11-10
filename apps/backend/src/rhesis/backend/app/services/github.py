import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import chardet
import requests
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

logger = logging.getLogger(__name__)

# read_repo_contents runs on a sync route, so it holds an anyio threadpool slot for
# the whole download. Without a timeout an unresponsive GitHub holds it forever and
# enough of those starve every sync route in the process.
_GITHUB_TIMEOUT_SECONDS = 30

_ALLOWED_HOSTS = frozenset({"github.com"})
# GitHub owner/repo/ref segment characters; also rules out "." and "..".
_SEGMENT_RE = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]+$")

# Caps per download, so one request cannot fill the disk or hold a worker for long.
_MAX_FILES = 500
_MAX_FILE_BYTES = 1_000_000
_MAX_TOTAL_BYTES = 10_000_000


class InvalidGitHubURL(ValueError):
    """The value is not an https://github.com/<owner>/<repo> URL."""


class RepositoryTooLarge(ValueError):
    """The repository exceeds the download caps."""


def _check_segments(segments: list[str]) -> None:
    if not all(_SEGMENT_RE.match(s) for s in segments):
        raise InvalidGitHubURL("Invalid GitHub URL")


def parse_github_url(github_url: str) -> tuple[str, str, str, str]:
    """Parse an https://github.com URL into (owner, repo, branch, subfolder).

    Anything else -- a local path, another scheme or host, credentials or a port
    in the URL -- raises InvalidGitHubURL.
    """
    try:
        parts = urlsplit(github_url)
        port = parts.port
    except ValueError as e:
        raise InvalidGitHubURL("Invalid GitHub URL") from e
    if (
        parts.scheme != "https"
        or (parts.hostname or "").lower() not in _ALLOWED_HOSTS
        or parts.username is not None
        or parts.password is not None
        or port is not None
    ):
        raise InvalidGitHubURL("Only https://github.com/<owner>/<repo> URLs are supported")

    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        raise InvalidGitHubURL("Invalid GitHub URL")
    _check_segments(segments)

    owner = segments[0]
    repo = segments[1].removesuffix(".git")
    _check_segments([repo])
    branch = "main"
    subfolder = ""

    remaining = segments[2:]
    if remaining and remaining[0] in ("tree", "blob"):
        # Format: /owner/repo/tree/branch/subfolder
        if len(remaining) > 1:
            branch = remaining[1]
            subfolder = "/".join(remaining[2:])
    elif remaining:
        # Format: /owner/repo/subfolder
        subfolder = "/".join(remaining)

    return owner, repo, branch, subfolder


def _fetch_tree(owner: str, repo: str, branch: str) -> tuple[str, list[dict]]:
    """Return (branch, tree), falling back from main to master."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    response = requests.get(api_url, timeout=_GITHUB_TIMEOUT_SECONDS)
    if response.status_code == 404 and branch == "main":
        branch = "master"
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        response = requests.get(api_url, timeout=_GITHUB_TIMEOUT_SECONDS)
    response.raise_for_status()
    return branch, response.json()["tree"]


def _select_blobs(tree: list[dict], subfolder: str) -> list[tuple[str, str]]:
    """Return (repo path, path relative to subfolder) for each file to download."""
    selected = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item["path"]
        if subfolder:
            if path == subfolder:
                relative = Path(path).name  # a /blob/<branch>/<file> URL
            elif path.startswith(subfolder + "/"):
                relative = path[len(subfolder) + 1 :]
            else:
                continue
        else:
            relative = path
        if item.get("size", 0) > _MAX_FILE_BYTES:
            continue
        selected.append((path, relative))
    if len(selected) > _MAX_FILES:
        raise RepositoryTooLarge(f"Repository has more than {_MAX_FILES} files")
    return selected


def download_github_repo(github_url: str, local_path: Path) -> None:
    """Download GitHub repository contents into local_path."""
    owner, repo, branch, subfolder = parse_github_url(github_url)
    branch, tree = _fetch_tree(owner, repo, branch)
    base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"

    root = Path(local_path).resolve()
    root.mkdir(parents=True, exist_ok=True)

    downloaded_files = 0
    total_bytes = 0
    for path, relative in _select_blobs(tree, subfolder):
        file_path = (root / relative).resolve()
        if not file_path.is_relative_to(root) or file_path == root:
            raise ValueError(f"Refusing to write outside the download directory: {path}")

        response = requests.get(f"{base_url}/{path}", timeout=_GITHUB_TIMEOUT_SECONDS)
        if response.status_code != 200:
            continue
        total_bytes += len(response.content)
        if total_bytes > _MAX_TOTAL_BYTES:
            raise RepositoryTooLarge(f"Repository is larger than {_MAX_TOTAL_BYTES} bytes")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(response.content)
        downloaded_files += 1

    logger.debug("Downloaded %d files from %s", downloaded_files, github_url)
    if downloaded_files == 0:
        raise ValueError(f"No files were downloaded from {github_url}")


def get_gitignore_spec(repo_path):
    """Get PathSpec from .gitignore if it exists"""
    gitignore_path = Path(repo_path) / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            return PathSpec.from_lines(GitWildMatchPattern, f)
    return PathSpec([])


def is_binary(file_path):
    """Check if a file is binary using chardet"""
    with open(file_path, "rb") as f:
        data = f.read(1024)
        return not bool(chardet.detect(data)["encoding"])


def should_skip_file(file_path):
    """Check if file should be skipped based on common patterns"""
    # Convert to lowercase for case-insensitive matching
    name = file_path.name.lower()
    path_str = str(file_path).lower()

    # Common files to skip
    skip_files = {
        "license",
        "licence",
        "copying",
        "notice",
        "readme.md",
        "changelog.md",
        "contributing.md",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "pyproject.toml",
        "poetry.lock",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "gemfile",
        "gemfile.lock",
        "cargo.toml",
        "cargo.lock",
        "composer.json",
        "composer.lock",
        ".dockerignore",
        "dockerfile",
        "docker-compose.yml",
        ".env",
        ".env.example",
        ".editorconfig",
    }

    # Skip patterns (directories or file extensions)
    skip_patterns = {
        "node_modules/",
        "venv/",
        ".venv/",
        "vendor/",
        "dist/",
        "build/",
        ".pytest_cache/",
        "__pycache__/",
        ".idea/",
        ".vscode/",
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dll",
        ".dylib",
    }

    # Direct filename match
    if name in skip_files:
        return True

    # Pattern matching
    return any(pattern in path_str for pattern in skip_patterns)


def _render_tree(repo_path: Path) -> str:
    """Concatenate the text files under repo_path, skipping binary and ignored files."""
    gitignore = get_gitignore_spec(repo_path)
    output = []

    for root, _, files in os.walk(repo_path):
        if ".git" in root:
            continue

        current_path = Path(root)
        rel_path = current_path.relative_to(repo_path)

        output.append(f"\n{'=' * 80}\nDirectory: {rel_path}\n{'=' * 80}\n")

        for file in files:
            file_path = current_path / file
            rel_file_path = file_path.relative_to(repo_path)

            # Skip files based on gitignore and our custom patterns
            if gitignore.match_file(str(rel_file_path)) or should_skip_file(rel_file_path):
                continue

            try:
                if is_binary(file_path):
                    output.append(f"[Binary file skipped]: {file}\n")
                    continue

                with open(file_path, "r", encoding="utf-8") as f:
                    output.append(f"\n{'-' * 40}\nFile: {rel_file_path}\n{'-' * 40}\n")
                    output.append(f.read() + "\n")
            except Exception as e:
                output.append(f"[Error reading file {file}]: {str(e)}\n")

    return "".join(output)


def read_repo_contents(github_url: str) -> str:
    """Download a GitHub repository and return its text contents as one string.

    Only https://github.com URLs are accepted (InvalidGitHubURL otherwise); a
    repository over the caps raises RepositoryTooLarge. Other download failures
    return "".
    """
    parse_github_url(github_url)
    temp_dir = Path(tempfile.mkdtemp(prefix="rhesis-github-"))
    try:
        try:
            download_github_repo(github_url, temp_dir)
        except RepositoryTooLarge:
            raise
        except Exception as e:
            logger.warning("Error downloading repository %s: %s", github_url, e)
            return ""
        return _render_tree(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
