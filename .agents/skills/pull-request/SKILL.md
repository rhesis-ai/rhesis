---
name: pull-request
description: Open a pull request in this repo — branch naming, title format, and the required description sections. Use when the user asks to create, open, or prep a PR.
---

# Pull Requests

- **An open PR is not a standing approval for more commits.** Once a PR exists, every additional
  commit or push to it — including small fixes requested after review — needs its own go-ahead
  from the user before you run `git commit`/`git push`, same as the first one.
- **Small PRs, one logical change each.** Ideal 1-200 lines, acceptable 200-400, break down 400+.
- Branch from latest `main`: `git fetch origin && git checkout main && git pull origin main &&
git checkout -b feature/your-feature-name`.
- Title: action verb first (Add/Fix/Update/Remove), under 72 characters.
- Write each paragraph as one continuous line — don't hard-wrap at a column width. `gh pr create
  --body`/`--body-file` sends newlines through verbatim, and GitHub renders each one as a line
  break, so a paragraph wrapped at ~100 characters shows up as choppy fragments instead of flowing
  text. Only break lines for real markdown structure: blank lines between sections, list items,
  headers, code blocks.
- Description must include these sections:

  ```markdown
  ## Purpose

  [Explain why this change is needed]

  ## What Changed

  - [Key change 1]

  ## Additional Context

  - [Links to issues, tickets, breaking changes]

  ## Testing

  [How to test these changes]
  ```
