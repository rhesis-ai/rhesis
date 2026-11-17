"""Polyphemus imports a few backend modules but installs the backend without the SDK.

Its image has ``rhesis-backend`` and no ``rhesis-sdk`` (apps/polyphemus/pyproject.toml), so
any module on the import path of these must not import the SDK at module level, or
Polyphemus fails to start. Runs in a subprocess with ``rhesis.sdk`` made unimportable.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3] / "apps" / "backend"

# What apps/polyphemus/src imports from the backend.
POLYPHEMUS_IMPORTS = [
    "rhesis.backend.app.auth.token_validation",
    "rhesis.backend.app.crud.user",
    "rhesis.backend.app.crud.token",
    "rhesis.backend.app.database",
    "rhesis.backend.app.models.user",
]

SCRIPT = """
import importlib.abc, sys

class NoSdk(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "rhesis.sdk" or name.startswith("rhesis.sdk."):
            raise ModuleNotFoundError(f"No module named {name!r}")

sys.meta_path.insert(0, NoSdk())
for module in sys.argv[1:]:
    __import__(module)
"""


def test_polyphemus_backend_imports_need_no_sdk():
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT, *POLYPHEMUS_IMPORTS],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
