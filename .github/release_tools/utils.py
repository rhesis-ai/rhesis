"""
Utilities for the Rhesis release tool including logging, colors, and prerequisites checking.
"""

import os
import subprocess
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Optional


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


def command_exists(command: str) -> bool:
    """Check if a command exists in PATH"""
    try:
        subprocess.run([command, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def load_env_var(env_file: Path, var_name: str) -> str:
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


def setup_python_env(repo_root: Path) -> bool:
    """Setup Python environment with TOML support"""
    # Try to use SDK virtual environment first
    sdk_venv = repo_root / "sdk" / ".venv" / "bin" / "activate"
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
    if command_exists("uv") and (repo_root / "sdk" / "pyproject.toml").exists():
        info("Installing tomli using uv in SDK environment")
        try:
            result = subprocess.run(
                ["uv", "add", "tomli"], 
                cwd=repo_root / "sdk",
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


def check_prerequisites(repo_root: Path, gemini_api_key: Optional[str] = None) -> tuple[bool, str]:
    """Check if all prerequisites are met and return API key"""
    # Check if in git repository
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], 
                     capture_output=True, check=True)
    except subprocess.CalledProcessError:
        error("Not in a git repository.")
        return False, ""
    
    # Check for required tools
    required_tools = ["git", "jq", "python3"]
    for tool in required_tools:
        if not command_exists(tool):
            error(f"{tool} is not installed. Please install it first.")
            return False, ""
    
    # Setup Python environment
    if not setup_python_env(repo_root):
        return False, ""
    
    # Check Gemini API key
    api_key = gemini_api_key or ""
    if not api_key:
        # First try .env file in repository root
        env_file = repo_root / ".env"
        if env_file.exists():
            api_key = load_env_var(env_file, "GEMINI_API_KEY")
            if api_key:
                info("Using Gemini API key from .env file")
        
        # Fallback to config file in home directory
        if not api_key:
            api_key_file = Path.home() / ".config" / "gemini-api-key"
            if api_key_file.exists():
                api_key = api_key_file.read_text().strip()
                if api_key:
                    info("Using Gemini API key from ~/.config/gemini-api-key")
        
        if not api_key:
            warn("No Gemini API key provided. Changelog generation will be skipped.")
            warn("Set GEMINI_API_KEY in .env file, environment variable, or use --gemini-key option.")
    
    return True, api_key


def call_gemini_api(api_key: str, prompt: str, max_tokens: int = 2048) -> Optional[str]:
    """Call Gemini API with the given prompt"""
    if not api_key:
        return None
    
    data = {
        'contents': [{
            'parts': [{'text': prompt}]
        }],
        'generationConfig': {
            'temperature': 0.3,
            'maxOutputTokens': max_tokens
        }
    }
    
    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-001:generateContent?key={api_key}'
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
        warn(f"Failed to generate content with LLM: HTTP {e.code} - {e.reason}")
        return None
    except Exception as e:
        warn(f"Failed to generate content with LLM: {e}")
        return None 