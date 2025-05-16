#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import chardet
import requests
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern


def parse_github_url(github_url):
    """Parse GitHub URL into components"""
    parts = urlparse(github_url).path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL")

    owner = parts[0]
    repo = parts[1]

    # Default values
    branch = "main"
    subfolder = ""

    remaining_parts = parts[2:]
    if remaining_parts:
        if remaining_parts[0] in ("tree", "blob"):
            # Format: /owner/repo/tree/branch/subfolder
            if len(remaining_parts) > 1:
                branch = remaining_parts[1]
                subfolder = "/".join(remaining_parts[2:]) if len(remaining_parts) > 2 else ""
        else:
            # Format: /owner/repo/subfolder
            subfolder = "/".join(remaining_parts)

    print(
        f"Parsed URL - Owner: {owner}, Repo: {repo}, Branch: {branch}, Subfolder: {subfolder}"
    )  # Debug line
    return owner, repo, branch, subfolder


def download_github_repo(github_url, local_path):
    """Download GitHub repository contents"""
    owner, repo, branch, subfolder = parse_github_url(github_url)

    # Try to get contents using the specified branch, fallback to 'master' if needed
    base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"

    # Create local directory
    os.makedirs(local_path, exist_ok=True)

    # Get the tree using GitHub API
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    response = requests.get(api_url)
    if response.status_code == 404 and branch == "main":
        # Fallback to master if main doesn't exist
        branch = "master"
        base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        response = requests.get(api_url)

    response.raise_for_status()

    downloaded_files = 0  # Debug counter
    tree = response.json()["tree"]
    for item in tree:
        if item["type"] != "blob":
            continue

        # Check if file is in the specified subfolder
        if subfolder:
            if not item["path"].startswith(subfolder):
                continue
            # Adjust the path to be relative to the subfolder
            relative_path = item["path"][len(subfolder) :].lstrip("/")
        else:
            relative_path = item["path"]

        file_path = Path(local_path) / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Download file content
        file_url = f"{base_url}/{item['path']}"
        print(f"Downloading: {file_url}")  # Debug line
        response = requests.get(file_url)
        if response.status_code == 200:
            file_path.write_bytes(response.content)
            downloaded_files += 1

    print(f"Downloaded {downloaded_files} files")  # Debug line
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


def read_repo_contents(repo_path):
    """Read repository contents, skipping binary and ignored files, and return as string"""
    # Handle GitHub URLs
    if repo_path.startswith("http"):
        temp_dir = Path("temp_repo")
        try:
            download_github_repo(repo_path, temp_dir)
            repo_path = temp_dir
        except Exception as e:
            print(f"Error downloading repository: {e}")
            return ""
    else:
        repo_path = Path(repo_path)

    if not Path(repo_path).exists():
        print(f"Error: Repository path {repo_path} does not exist!")
        return ""

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

    # Cleanup if we downloaded a repo
    if repo_path.name == "temp_repo":
        import shutil

        shutil.rmtree(repo_path)

    return "".join(output)


def main():
    if len(sys.argv) != 2:
        print("Usage: python git_contents_reader.py <repo_path_or_url>")
        sys.exit(1)

    contents = read_repo_contents(sys.argv[1])
    print(contents)


if __name__ == "__main__":
    main()
