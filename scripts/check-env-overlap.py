#!/usr/bin/env python3
"""Fail when an env key is defined in both a rendered ConfigMap and an ExternalSecret.

Kubernetes gives later envFrom sources precedence, so a key duplicated across
the chart ConfigMap and an ExternalSecret silently shadows values-*.yaml edits.
The allowlist below pins the duplicates that still exist today (see issue
#2420); removing a duplicate without shrinking the allowlist fails this check,
so the list cannot go stale.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

ENVS = ("dev", "stg", "prd")

# env -> keys duplicated between ConfigMap and ExternalSecret today.
# Shrink as each duplicate is resolved; the check fails if this drifts.
ALLOWLIST: dict[str, set[str]] = {
    "dev": {"APP_DB_USER", "DB_HOST", "DB_NAME", "OTEL_PROCESSOR_ENDPOINT"},
    "stg": {
        "ANALYTICS_DB_HOST",
        "ANALYTICS_DB_NAME",
        "ANALYTICS_DB_PORT",
        "OTEL_PROCESSOR_ENDPOINT",
    },
    "prd": {
        "ANALYTICS_DB_HOST",
        "ANALYTICS_DB_NAME",
        "ANALYTICS_DB_PORT",
        "OTEL_PROCESSOR_ENDPOINT",
    },
}


def configmap_keys(env: str) -> set[str]:
    rendered = subprocess.run(
        [
            "helm",
            "template",
            "rhesis",
            "charts/rhesis",
            "-f",
            f"charts/rhesis/values-{env}.yaml",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    keys: set[str] = set()
    for doc in yaml.safe_load_all(rendered):
        if isinstance(doc, dict) and doc.get("kind") == "ConfigMap":
            keys.update((doc.get("data") or {}).keys())
    return keys


def externalsecret_keys(env: str) -> set[str]:
    keys: set[str] = set()
    secrets_dir = REPO_ROOT / "kubernetes" / "clusters" / env / "external-secrets"
    for manifest in secrets_dir.glob("*.yaml"):
        for doc in yaml.safe_load_all(manifest.read_text()):
            if not isinstance(doc, dict) or doc.get("kind") != "ExternalSecret":
                continue
            for entry in doc.get("spec", {}).get("data") or []:
                key = entry.get("secretKey") or (entry.get("remoteRef") or {}).get("key")
                if key:
                    keys.add(key)
    return keys


def main() -> int:
    failed = False
    for env in ENVS:
        overlap = configmap_keys(env) & externalsecret_keys(env)
        allowed = ALLOWLIST[env]
        new = overlap - allowed
        stale = allowed - overlap
        if new:
            failed = True
            print(f"{env}: new ConfigMap/ExternalSecret overlap: {sorted(new)}")
        if stale:
            failed = True
            print(f"{env}: allowlist keys no longer overlap (remove them): {sorted(stale)}")
        if not new and not stale:
            print(f"{env}: OK ({len(overlap)} allowlisted overlap(s))")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
