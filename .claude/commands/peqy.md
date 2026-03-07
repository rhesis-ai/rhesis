---
description: Review peqy bot comments on a PR and assess their validity against the codebase
---

Review the comments left by peqy[bot] on a pull request and assess whether each comment is valid, actionable, and consistent with the codebase's existing patterns.

## Steps

1. Determine the PR number:
   - If `$ARGUMENTS` is provided, use it as the PR number
   - Otherwise, detect the current branch and find its open PR using `gh pr view --json number`

2. Fetch all review comments from peqy using:
   ```
   gh api repos/rhesis-ai/rhesis/pulls/{PR_NUMBER}/comments
   ```
   Filter to comments from `peqy[bot]`.

3. For each comment:
   - Read the file and lines referenced in the comment
   - Investigate the surrounding codebase for existing patterns and conventions
   - Assess validity considering:
     - Does the suggestion match existing patterns in the codebase?
     - Would applying it introduce inconsistency (e.g. adding a comment only in one place when the same pattern exists uncommented elsewhere)?
     - Is the concern real or theoretical?
     - Does it conflict with project conventions in CLAUDE.md?
   - Classify as: **Valid** (worth fixing), **Marginal** (technically correct but not worth changing), or **Invalid** (wrong or inconsistent with codebase)

4. Present a summary table:

   | # | Comment | File | Verdict | Reasoning |
   |---|---------|------|---------|-----------|

5. For comments classified as **Valid**, ask the user if they want them applied.
