#!/usr/bin/env python3
"""
Rhesis Platform Release Tool

This script manages releases for individual components and platform-wide releases
with automatic version bumping, changelog generation, and git tagging.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ANSI color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color


def log(message: str) -> None:
    print(f"{Colors.BLUE}[RELEASE]{Colors.NC} {message}")


def warn(message: str) -> None:
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")


def error(message: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


def success(message: str) -> None:
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def info(message: str) -> None:
    print(f"{Colors.CYAN}[INFO]{Colors.NC} {message}")


class ComponentConfig:
    """Configuration for a component"""
    def __init__(self, config_file: str, config_type: str, changelog_path: str):
        self.config_file = config_file
        self.config_type = config_type
        self.changelog_path = changelog_path


class ReleaseManager:
    """Main release management class"""
    
    def __init__(self, repo_root: Path, dry_run: bool = False, gemini_api_key: str = "", no_branch: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.gemini_api_key = gemini_api_key
        self.no_branch = no_branch
        
        # Component configurations
        self.components = {
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
                "apps/polyphemus/requirements.txt", "requirements", "apps/polyphemus/CHANGELOG.md"
            ),
            "sdk": ComponentConfig(
                "sdk/pyproject.toml", "pyproject", "sdk/CHANGELOG.md"
            ),
        }
        
        self.platform_version_file = "VERSION"
        self.platform_changelog = "CHANGELOG.md"
        
        # Component versions and bumps
        self.component_versions: Dict[str, str] = {}
        self.component_bumps: Dict[str, str] = {}

    def format_component_name(self, component: str) -> str:
        """Format component name with proper capitalization"""
        if component.lower() == "sdk":
            return "SDK"
        return component.title()

    def setup_python_env(self) -> bool:
        """Setup Python environment with TOML support"""
        # Try to use SDK virtual environment first
        sdk_venv = self.repo_root / "sdk" / ".venv" / "bin" / "activate"
        if sdk_venv.exists():
            try:
                import tomli
                info("Using SDK virtual environment with tomli")
                return True
            except ImportError:
                pass
        
        # Check if tomli is available globally
        try:
            import tomli
            info("Using global Python environment with tomli")
            return True
        except ImportError:
            pass
        
        # Check if toml is available globally
        try:
            import toml
            info("Using global Python environment with toml")
            return True
        except ImportError:
            pass
        
        # Try to install tomli using uv if not already available
        if self._command_exists("uv") and (self.repo_root / "sdk" / "pyproject.toml").exists():
            info("Installing tomli using uv in SDK environment")
            try:
                result = subprocess.run(
                    ["uv", "add", "tomli"], 
                    cwd=self.repo_root / "sdk",
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    info("Successfully installed tomli using uv")
                    return True
            except Exception as e:
                warn(f"Failed to install with uv: {e}")
        
        error("No TOML library available. Please install tomli:")
        error("  - For SDK: cd sdk && uv add tomli")
        error("  - Globally: pip3 install tomli")
        return False

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _load_env_var(self, env_file: Path, var_name: str) -> str:
        """Load environment variable from .env file"""
        try:
            content = env_file.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith(f"{var_name}="):
                    # Handle quoted and unquoted values
                    value = line.split("=", 1)[1]
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    return value
        except Exception as e:
            warn(f"Failed to read .env file: {e}")
        return ""

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        # Check if in git repository
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], 
                         capture_output=True, check=True)
        except subprocess.CalledProcessError:
            error("Not in a git repository.")
            return False
        
        # Check for required tools
        required_tools = ["git", "jq", "python3"]
        for tool in required_tools:
            if not self._command_exists(tool):
                error(f"{tool} is not installed. Please install it first.")
                return False
        
        # Setup Python environment
        if not self.setup_python_env():
            return False
        
        # Check Gemini API key
        if not self.gemini_api_key:
            # First try .env file in repository root
            env_file = self.repo_root / ".env"
            if env_file.exists():
                self.gemini_api_key = self._load_env_var(env_file, "GEMINI_API_KEY")
                if self.gemini_api_key:
                    info("Using Gemini API key from .env file")
            
            # Fallback to config file in home directory
            if not self.gemini_api_key:
                api_key_file = Path.home() / ".config" / "gemini-api-key"
                if api_key_file.exists():
                    self.gemini_api_key = api_key_file.read_text().strip()
                    if self.gemini_api_key:
                        info("Using Gemini API key from ~/.config/gemini-api-key")
            
            if not self.gemini_api_key:
                warn("No Gemini API key provided. Changelog generation will be skipped.")
                warn("Set GEMINI_API_KEY in .env file, environment variable, or use --gemini-key option.")
        
        return True

    def get_current_version(self, component: str) -> str:
        """Get current version of a component"""
        if component == "platform":
            version_file = self.repo_root / self.platform_version_file
            if version_file.exists():
                return version_file.read_text().strip() or "0.0.0"
            return "0.0.0"
        
        if component not in self.components:
            raise ValueError(f"Unknown component: {component}")
        
        config = self.components[component]
        config_path = self.repo_root / config.config_file
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        if config.config_type == "pyproject":
            return self._get_pyproject_version(config_path)
        elif config.config_type == "package":
            return self._get_package_version(config_path)
        elif config.config_type == "requirements":
            return "0.1.0"  # Default for requirements.txt based components
        
        return "0.1.0"

    def _get_pyproject_version(self, config_path: Path) -> str:
        """Get version from pyproject.toml"""
        try:
            import tomli
            with open(config_path, 'rb') as f:
                data = tomli.load(f)
            return data['project']['version']
        except ImportError:
            try:
                import toml
                with open(config_path, 'r') as f:
                    data = toml.load(f)
                return data['project']['version']
            except ImportError:
                pass
        except Exception:
            pass
        return "0.1.0"

    def _get_package_version(self, config_path: Path) -> str:
        """Get version from package.json"""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            return data.get('version', '0.1.0')
        except Exception:
            return "0.1.0"

    def bump_version(self, current_version: str, bump_type: str) -> str:
        """Bump version according to semantic versioning"""
        version_parts = current_version.split('.')
        major = int(version_parts[0]) if len(version_parts) > 0 else 0
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        patch = int(version_parts[2]) if len(version_parts) > 2 else 0
        
        if bump_type == "patch":
            patch += 1
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        
        return f"{major}.{minor}.{patch}"

    def update_version_file(self, component: str, new_version: str) -> bool:
        """Update version in configuration file"""
        if component == "platform":
            if self.dry_run:
                info(f"Would update {self.platform_version_file} to: {new_version}")
                return True
            
            version_file = self.repo_root / self.platform_version_file
            version_file.write_text(new_version)
            success(f"Updated {self.platform_version_file} to: {new_version}")
            return True
        
        config = self.components[component]
        config_path = self.repo_root / config.config_file
        
        if self.dry_run:
            info(f"Would update {config.config_file} version to: {new_version}")
            return True
        
        if config.config_type == "pyproject":
            return self._update_pyproject_version(config_path, new_version)
        elif config.config_type == "package":
            return self._update_package_version(config_path, new_version)
        elif config.config_type == "requirements":
            info(f"Component {component} uses requirements.txt - version tracked via git tags only")
            return True
        
        return False

    def _update_pyproject_version(self, config_path: Path, new_version: str) -> bool:
        """Update version in pyproject.toml"""
        try:
            # Try using tomli/tomli_w
            try:
                import tomli
                import tomli_w
                
                with open(config_path, 'rb') as f:
                    data = tomli.load(f)
                
                data['project']['version'] = new_version
                
                with open(config_path, 'wb') as f:
                    tomli_w.dump(data, f)
                
                success(f"Updated {config_path.relative_to(self.repo_root)} version to: {new_version}")
                return True
                
            except ImportError:
                # Fallback to regex replacement
                content = config_path.read_text()
                pattern = r'(version\s*=\s*)["\']([^"\']*)["\']'
                new_content = re.sub(pattern, rf'\1"{new_version}"', content)
                config_path.write_text(new_content)
                success(f"Updated {config_path.relative_to(self.repo_root)} version to: {new_version}")
                return True
                
        except Exception as e:
            error(f"Failed to update {config_path}: {e}")
            return False

    def _update_package_version(self, config_path: Path, new_version: str) -> bool:
        """Update version in package.json"""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            data['version'] = new_version
            
            with open(config_path, 'w') as f:
                json.dump(data, f, indent=4)
            
            success(f"Updated {config_path.relative_to(self.repo_root)} version to: {new_version}")
            return True
            
        except Exception as e:
            error(f"Failed to update {config_path}: {e}")
            return False

    def get_last_tag(self, component: str) -> Optional[str]:
        """Get the last git tag for a component"""
        if component == "platform":
            tag_pattern = "v*"
        else:
            tag_pattern = f"{component}-v*"
        
        try:
            result = subprocess.run(
                ["git", "tag", "-l", tag_pattern], 
                capture_output=True, text=True, check=True
            )
            tags = result.stdout.strip().split('\n') if result.stdout.strip() else []
            if tags:
                # Sort tags by version
                return sorted(tags, key=lambda x: [int(i) for i in re.findall(r'\d+', x)])[-1]
            return None
        except subprocess.CalledProcessError:
            return None

    def get_commits_since_tag(self, component: str, last_tag: Optional[str]) -> List[Dict[str, str]]:
        """Get commits since last tag for a component"""
        # Define component paths
        component_paths = {
            "backend": "apps/backend",
            "frontend": "apps/frontend", 
            "worker": "apps/worker",
            "chatbot": "apps/chatbot",
            "polyphemus": "apps/polyphemus",
            "sdk": "sdk",
            "platform": "."
        }
        
        component_path = component_paths.get(component, ".")
        
        git_range = f"{last_tag}..HEAD" if last_tag else "HEAD"
        
        try:
            cmd = ["git", "log", "--pretty=format:%H|%an|%ai|%s", git_range]
            if component != "platform":
                cmd.extend(["--", component_path])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|', 3)
                    if len(parts) == 4:
                        commits.append({
                            'hash': parts[0],
                            'author': parts[1],
                            'date': parts[2],
                            'message': parts[3]
                        })
            
            return commits
            
        except subprocess.CalledProcessError:
            return []

    def generate_changelog_with_llm(self, component: str, version: str, 
                                  commits: List[Dict[str, str]], last_tag: Optional[str]) -> Optional[str]:
        """Generate changelog using Gemini API"""
        if not self.gemini_api_key:
            warn(f"No Gemini API key available. Skipping LLM changelog generation for {component}")
            return None
        
        commits_text = "\n".join([
            f"- {commit['message']} ({commit['hash'][:8]}, {commit['author']})"
            for commit in commits
        ])
        
        prompt = f"""Generate a professional changelog entry for version {version} of the {self.format_component_name(component)} component in a software project.

Based on these commits since the last release{f' ({last_tag})' if last_tag else ''}:

{commits_text}

Please format the output as a markdown changelog section following the 'Keep a Changelog' format. Include appropriate categories like Added, Changed, Fixed, Removed, etc. Be concise but informative. Focus on user-facing changes and improvements.

Do NOT include the version header line (## [version] - date) - only return the content sections (### Added, ### Changed, etc.). 

Return ONLY the changelog content without any additional text or explanations."""

        data = {
            'contents': [{
                'parts': [{'text': prompt}]
            }],
            'generationConfig': {
                'temperature': 0.3,
                'maxOutputTokens': 2048
            }
        }
        
        try:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-001:generateContent?key={self.gemini_api_key}'
            req = urllib.request.Request(url)
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, json.dumps(data).encode()) as response:
                result = json.loads(response.read().decode())
                if 'candidates' in result and len(result['candidates']) > 0:
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    warn("No content generated by LLM")
                    return None
                    
        except urllib.error.HTTPError as e:
            warn(f"Failed to generate changelog with LLM: HTTP {e.code} - {e.reason}")
            return None
        except Exception as e:
            warn(f"Failed to generate changelog with LLM: {e}")
            return None

    def generate_component_summary_with_llm(self, component: str, version: str, 
                                          commits: List[Dict[str, str]], last_tag: Optional[str]) -> Optional[str]:
        """Generate a brief component summary for platform changelog using Gemini API"""
        if not self.gemini_api_key:
            return None
        
        commits_text = "\n".join([
            f"- {commit['message']} ({commit['hash'][:8]}, {commit['author']})"
            for commit in commits
        ])
        
        prompt = f"""Generate a brief bullet point summary of changes for version {version} of the {self.format_component_name(component)} component.

Based on these commits since the last release{f' ({last_tag})' if last_tag else ''}:

{commits_text}

Focus on the most important user-facing changes and improvements. Format as 2-4 bullet points using simple dashes (-). Keep each point concise and informative.

Return ONLY the bullet points without any additional text or explanations."""

        data = {
            'contents': [{
                'parts': [{'text': prompt}]
            }],
            'generationConfig': {
                'temperature': 0.3,
                'maxOutputTokens': 512
            }
        }
        
        try:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-001:generateContent?key={self.gemini_api_key}'
            req = urllib.request.Request(url)
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, json.dumps(data).encode()) as response:
                result = json.loads(response.read().decode())
                if 'candidates' in result and len(result['candidates']) > 0:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
                else:
                    return None
                    
        except urllib.error.HTTPError as e:
            warn(f"Failed to generate component summary with LLM: HTTP {e.code} - {e.reason}")
            return None
        except Exception as e:
            warn(f"Failed to generate component summary with LLM: {e}")
            return None

    def generate_fallback_changelog(self, version: str, commits: List[Dict[str, str]]) -> str:
        """Generate fallback changelog from commits"""
        date = datetime.now().strftime("%Y-%m-%d")
        
        changelog = f"## [{version}] - {date}\n\n### Changed\n\n"
        
        if commits:
            for commit in commits:
                changelog += f"- {commit['message']}\n"
        else:
            changelog += "- Initial release\n"
        
        changelog += "\n"
        return changelog

    def update_component_changelog(self, component: str, new_version: str, changelog_content: str) -> bool:
        """Update component changelog"""
        if component not in self.components:
            warn(f"No changelog path defined for component: {component}")
            return False
        
        changelog_path = self.repo_root / self.components[component].changelog_path
        
        if self.dry_run:
            info(f"Would update changelog: {self.components[component].changelog_path}")
            info("New content:")
            print("\n".join(changelog_content.split('\n')[:10]))
            return True
        
        # Create changelog if it doesn't exist
        if not changelog_path.exists():
            changelog_path.parent.mkdir(parents=True, exist_ok=True)
            
            header = f"""# {self.format_component_name(component)} Changelog

All notable changes to the {component} component will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

"""
            changelog_path.write_text(header)
        
        # Insert new changelog entry after [Unreleased] section
        content = changelog_path.read_text()
        lines = content.split('\n')
        
        new_lines = []
        inserted = False
        
        for line in lines:
            new_lines.append(line)
            if line.strip() == "## [Unreleased]" and not inserted:
                new_lines.append("")
                new_lines.extend(changelog_content.split('\n'))
                inserted = True
        
        changelog_path.write_text('\n'.join(new_lines))
        success(f"Updated changelog: {self.components[component].changelog_path}")
        return True

    def update_platform_changelog(self, new_version: str) -> bool:
        """Update platform changelog"""
        if self.dry_run:
            info(f"Would update platform changelog: {self.platform_changelog}")
            info("Platform changelog would include LLM-generated summaries for each component")
            return True
        
        changelog_path = self.repo_root / self.platform_changelog
        date = datetime.now().strftime("%Y-%m-%d")
        
        # Generate platform changelog entry
        platform_entry = f"""## [{new_version}] - {date}

### Platform Release

This release includes the following component versions:
"""
        
        # Add component versions
        for component, version in self.component_versions.items():
            if component != "platform":
                platform_entry += f"- **{self.format_component_name(component)} {version}**\n"
        
        platform_entry += "\n### Summary of Changes\n\n"
        
        # Generate summaries for each component
        for component, version in self.component_versions.items():
            if component != "platform":
                # Get commit history for this component
                last_tag = self.get_last_tag(component)
                commits = self.get_commits_since_tag(component, last_tag)
                
                component_name = self.format_component_name(component)
                platform_entry += f"**{component_name} v{version}:**\n"
                
                # Try to generate LLM summary
                summary = None
                if self.gemini_api_key and commits:
                    summary = self.generate_component_summary_with_llm(
                        component, version, commits, last_tag
                    )
                
                if summary:
                    platform_entry += f"{summary}\n\n"
                elif commits:
                    # Fallback to first few commit messages
                    commit_msgs = [commit['message'] for commit in commits[:3]]
                    platform_entry += f"Key changes include: {', '.join(commit_msgs[:2])}{'...' if len(commits) > 2 else ''}.\n\n"
                else:
                    platform_entry += "Initial release or no significant changes.\n\n"
        
        platform_entry += "See individual component changelogs for detailed changes:\n"
        
        for component in self.component_versions:
            if component != "platform" and component in self.components:
                changelog_path_rel = self.components[component].changelog_path
                platform_entry += f"- [{self.format_component_name(component)} Changelog]({changelog_path_rel})\n"
        
        platform_entry += "\n"
        
        # Insert into changelog
        content = changelog_path.read_text()
        lines = content.split('\n')
        
        new_lines = []
        inserted = False
        
        for line in lines:
            new_lines.append(line)
            if line.strip() == "## [Unreleased]" and not inserted:
                new_lines.append("")
                new_lines.extend(platform_entry.split('\n'))
                inserted = True
        
        changelog_path.write_text('\n'.join(new_lines))
        success(f"Updated platform changelog: {self.platform_changelog}")
        return True

    def create_release_branch(self) -> bool:
        """Create appropriate release branch based on components and versions"""
        # Check if we're on main branch
        try:
            current_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, check=True
            ).stdout.strip()
        except subprocess.CalledProcessError:
            error("Failed to get current branch")
            return False
        
        # If already on a release branch, skip creation
        if current_branch.startswith("release/"):
            info(f"Already on release branch: {current_branch}")
            return True
        
        # If not on main, warn but continue
        if current_branch != "main":
            warn(f"Not on main branch (currently on: {current_branch})")
            if not self.dry_run:
                response = input("Continue anyway? (y/N): ").strip().lower()
                if response != 'y':
                    info("Release cancelled")
                    return False
        
        # Generate branch name based on release components
        branch_name = self.generate_branch_name()
        
        if self.dry_run:
            info(f"Would create release branch: {branch_name}")
            return True
        
        # Check if branch already exists
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
                capture_output=True, check=True
            )
            error(f"Branch {branch_name} already exists")
            return False
        except subprocess.CalledProcessError:
            # Branch doesn't exist, which is what we want
            pass
        
        # Create and checkout the branch
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], check=True)
            success(f"Created and switched to branch: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            error(f"Failed to create branch {branch_name}: {e}")
            return False
    
    def generate_branch_name(self) -> str:
        """Generate appropriate branch name based on release components"""
        import hashlib
        
        # Get target versions for all components
        component_versions = []
        unique_versions = set()
        
        for component, bump_type in self.component_bumps.items():
            current_version = self.get_current_version(component)
            if not current_version:
                continue
            new_version = self.bump_version(current_version, bump_type)
            component_versions.append((component, new_version))
            unique_versions.add(new_version)
        
        # Determine branch naming strategy
        if len(component_versions) == 1:
            # Single component
            component, version = component_versions[0]
            if component == "platform":
                return f"release/v{version}"
            else:
                return f"release/{component}-v{version}"
        
        elif "platform" in [comp for comp, _ in component_versions]:
            # Platform release
            platform_version = next(ver for comp, ver in component_versions if comp == "platform")
            return f"release/v{platform_version}"
        
        elif len(unique_versions) == 1:
            # Multiple components, same version
            version = unique_versions.pop()
            return f"release/multi-v{version}"
        
        else:
            # Multiple components, different versions
            # Use a short hash of component names for uniqueness
            component_names = sorted([comp for comp, _ in component_versions])
            hash_input = "-".join(component_names)
            short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:6]
            return f"release/multi-{short_hash}"

    def process_releases(self) -> bool:
        """Process all releases"""
        log("Starting release process...")
        
        # First pass: collect current versions and calculate new versions
        for component, bump_type in self.component_bumps.items():
            current_version = self.get_current_version(component)
            new_version = self.bump_version(current_version, bump_type)
            
            self.component_versions[component] = new_version
            
            info(f"Component: {component}")
            info(f"  Current version: {current_version}")
            info(f"  Bump type: {bump_type}")
            info(f"  New version: {new_version}")
            print()
        
        if self.dry_run:
            warn("DRY RUN MODE - No changes will be made")
            print()
        
        # Second pass: update versions and changelogs
        for component, new_version in self.component_versions.items():
            log(f"Processing release for {component} v{new_version}...")
            
            # Update version files
            if not self.update_version_file(component, new_version):
                return False
            
            # Get commit history
            last_tag = self.get_last_tag(component)
            commits = self.get_commits_since_tag(component, last_tag)
            
            info(f"Last tag for {component}: {last_tag or '(none)'}")
            
            if commits:
                info(f"Found {len(commits)} commits since last release")
            else:
                info("No commits found since last release")
            
            # Generate changelog (skip for platform-wide releases)
            if component != "platform":
                changelog_content = None
                
                # Try LLM generation first
                if self.gemini_api_key:
                    llm_content = self.generate_changelog_with_llm(
                        component, new_version, commits, last_tag
                    )
                    if llm_content:
                        # Add proper header with current date to LLM-generated content
                        date = datetime.now().strftime("%Y-%m-%d")
                        changelog_content = f"## [{new_version}] - {date}\n\n{llm_content.strip()}\n"
                
                # Fall back to basic changelog if LLM failed
                if not changelog_content:
                    changelog_content = self.generate_fallback_changelog(new_version, commits)
                
                # Update component changelog
                if not self.update_component_changelog(component, new_version, changelog_content):
                    return False
            
            info(f"Version and changelog updated for {component} v{new_version}")
            
            success(f"Completed release for {component} v{new_version}")
            print()
        
        # Handle platform changelog if platform was included
        if "platform" in self.component_bumps:
            platform_version = self.component_versions.get("platform")
            if platform_version:
                self.update_platform_changelog(platform_version)
        
        return True

    def run(self, component_bumps: Dict[str, str]) -> bool:
        """Main entry point"""
        self.component_bumps = component_bumps
        
        if not self.check_prerequisites():
            return False
        
        # Create release branch if needed (unless --no-branch specified)
        if not self.no_branch:
            if not self.create_release_branch():
                return False
        
        log("Rhesis Platform Release Tool")
        log(f"Repository: {self.repo_root}")
        
        if self.dry_run:
            warn("Running in DRY RUN mode")
        
        print()
        
        if not self.process_releases():
            return False
        
        print()
        success("Release process completed! 🎉")
        
        if not self.dry_run:
            print()
            info("Next steps:")
            info("1. Review the changes made to version files and changelogs")
            info('2. Commit the changes: git add . && git commit -m "Prepare release: <description>"')
            info("3. Push and create PR: git push origin $(git branch --show-current) && ./.github/create-pr.sh")
            info("4. After PR merge, create tags and releases using separate tooling")
        
        return True


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Rhesis Platform Release Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s backend --minor frontend --patch sdk --major
  %(prog)s --dry-run backend --patch frontend --minor platform --major
  %(prog)s --no-branch sdk --patch  # Skip branch creation

Components:
  backend, frontend, worker, chatbot, polyphemus, sdk
  platform (for platform-wide releases)

Version Types:
  --patch   (0.0.X)
  --minor   (0.X.0)  
  --major   (X.0.0)
        """
    )
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--no-branch', action='store_true',
                       help='Skip automatic release branch creation')

    parser.add_argument('--gemini-key', type=str,
                       help='Gemini API key for changelog generation')
    
    # Parse known args to handle component arguments
    args, remaining = parser.parse_known_args()
    
    # Parse component arguments
    component_bumps = {}
    i = 0
    while i < len(remaining):
        if remaining[i] in ['backend', 'frontend', 'worker', 'chatbot', 'polyphemus', 'sdk', 'platform']:
            component = remaining[i]
            if i + 1 < len(remaining) and remaining[i + 1] in ['--patch', '--minor', '--major']:
                bump_type = remaining[i + 1][2:]  # Remove --
                component_bumps[component] = bump_type
                i += 2
            else:
                error(f"Missing version type for component: {component}")
                error("Must be one of: --patch, --minor, --major")
                return 1
        else:
            error(f"Unknown argument: {remaining[i]}")
            parser.print_help()
            return 1
    
    if not component_bumps:
        error("No components specified for release")
        parser.print_help()
        return 1
    
    # Get Gemini API key from environment if not provided
    gemini_key = args.gemini_key or os.environ.get('GEMINI_API_KEY', '')
    
    # Find repository root
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / '.git').exists():
            break
        repo_root = repo_root.parent
    else:
        error("Not in a git repository")
        return 1
    
    # Create release manager and run
    manager = ReleaseManager(repo_root, args.dry_run, gemini_key, args.no_branch)
    
    try:
        success = manager.run(component_bumps)
        return 0 if success else 1
    except KeyboardInterrupt:
        error("Operation cancelled by user")
        return 1
    except Exception as e:
        error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main()) 