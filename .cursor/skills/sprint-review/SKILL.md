---
name: sprint-review
description: Generate a sprint review changelog from GitHub pull requests. Lists PRs by a given author since a given date, groups them into Features and Fixes, and writes a markdown summary.
disable-model-invocation: true
---

# Sprint Review

Generate a markdown changelog from GitHub PRs for sprint review meetings.

## Defaults

- **Time range**: last two weeks (14 days from today)
- **Author**: the current GitHub user -- detect automatically via `gh api user --jq .login`

Both can be overridden if the user explicitly provides a different author or date.

## Workflow

1. **Detect the current user** (unless explicitly provided):

```bash
gh api user --jq .login
```

2. **Collect PRs** using GitHub CLI (default: last 14 days):

```bash
gh pr list --author <username> --state all --search "created:>=<date>" --limit 100 \
  --json number,title,state,createdAt,body,url \
  | jq -r '.[] | "\(.number)|\(.title)|\(.state)|\(.createdAt)|\(.url)"'
```

3. **Fetch PR bodies** for context on what each PR does (use `--json body`).

4. **Group PRs** into two sections:
   - **Features** -- new capabilities, refactors, new providers, new APIs
   - **Fixes** -- bug fixes, dependency patches, config corrections, minor chores

5. **Consolidate similar PRs** under a single description when they share the same goal (e.g. two PRs making different parts of the SDK async-first).

6. **Write the markdown file** to `docs/changelog-<username>.md` using this format:

```markdown
## PR Changelog -- <username> (<start date> -- <end date>)

### Features

**Short heading**

One-to-two sentence description.

- [#<number> -- <title>](<url>)
- [#<number> -- <title>](<url>) *(open/draft if not merged)*

### Fixes

**Short heading**

One sentence description.

- [#<number> -- <title>](<url>)
```

## Formatting rules

- Section headings: `###` for Features / Fixes
- Entry headings: **bold text** (not a markdown heading)
- Descriptions: 1-2 sentences max, focus on what changed and why it matters
- PR links: bulleted list with `#<number> -- <title>` as link text
- Mark non-merged PRs with *(open)* or *(draft)*
- No emojis
