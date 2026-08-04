---
name: playground-script
description: Write an ad-hoc script under playground/ for manual testing or prototyping against the SDK. Use when the user asks for a playground or throwaway test script.
---

# Playground Scripts (`playground/`, when present)

Ad-hoc scripts for manual testing/prototyping — not part of the production codebase or automated
test suite. They import from the SDK, so run them from `sdk/`:

```bash
cd sdk && uv run python ../playground/<script_name>.py
```

Each script needs a top docstring (purpose, prerequisites, how to run). Hardcoded local URLs/keys
are fine. Never add these scripts to the automated test suite.
