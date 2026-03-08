---
description: Audit and fix Dependabot security vulnerabilities across the monorepo
---

Audit and fix security vulnerabilities reported by GitHub Dependabot for this repository.

## Steps

1. **Fetch all open Dependabot alerts** using `gh api repos/rhesis-ai/rhesis/dependabot/alerts` and group them by package name, showing: package, ecosystem, severity, affected manifests, patched version, and summary.

2. **Classify each vulnerability** into one of these categories:
   - **Direct dependency bump**: The vulnerable package is declared in pyproject.toml or package.json and can be upgraded.
   - **Transitive override**: The vulnerable package is a transitive dependency — fix via npm `overrides` or uv `constraint-dependencies`.
   - **Unused dependency**: The vulnerable package (or its parent) is no longer used and can be removed. Ask the user to confirm before removing.
   - **No patch available**: No fixed version exists upstream. Flag for monitoring only.
   - **Major version upgrade**: A fix exists but requires a major version bump that may break things. Flag for separate evaluation.

3. **Present a summary table** to the user grouped by category, showing the fix approach and risk level for each. Ask the user which groups to proceed with.

4. **Apply fixes** in this order:
   - **Python direct deps**: Use `uv lock --upgrade-package <pkg>` in the affected project directories. If a version pin in pyproject.toml blocks the upgrade, relax the pin (e.g. `==X.Y.Z` to `>=X.Y.Z`) and explain why.
   - **Remove unused deps**: Remove from package.json/pyproject.toml and regenerate lockfiles.
   - **npm transitive deps**: Add or update entries in the `overrides` section of package.json, then run `npm install --package-lock-only` to regenerate the lockfile.
   - **Python transitive deps**: Add or update entries in `[tool.uv] constraint-dependencies` in pyproject.toml, then run `uv lock`.

5. **Verify each fix**:
   - For npm: confirm `npm install --package-lock-only` reports 0 new vulnerabilities (pre-existing unrelated ones are acceptable).
   - For Python: confirm the lockfile shows the patched version using `grep -A1 'name = "<pkg>"' uv.lock`.

6. **Show a final summary** of: alerts resolved, alerts remaining (with reason), and all files changed (`git diff --stat`).

## Important rules

- Never modify lockfiles by hand — always regenerate them with `npm install --package-lock-only` or `uv lock`.
- When relaxing a version pin, use `>=current_version` rather than removing the constraint entirely.
- For npm overrides, set the minimum to the exact patched version from the advisory (e.g. `>=3.1.3`).
- Run Python lock commands from the project directory containing the pyproject.toml, not the repo root.
- Do not auto-commit. Present the changes and let the user decide.
