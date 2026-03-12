---
name: sprint-review
description: Generate a sprint review changelog from GitHub pull requests for all authors and save it to Notion.
disable-model-invocation: true
---

# Sprint Review

Generate a changelog from GitHub pull requests for sprint review meetings, grouped by author,
then save it to Notion using the sprint review template.

## Inputs

- `days` (optional): number of days back from today (default: 14)
- `end_date` (optional): ISO date `YYYY-MM-DD` in UTC (default: today UTC)
- `repo` (optional): `owner/repo` to scope PRs (default: all accessible repos)

## Date range rules

- Use UTC dates only.
- `end_date` defaults to today (UTC).
- `start_date = end_date - (days - 1)` days.
- Filter PRs with inclusive range: `created:<start_date>..<end_date>`.

## Workflow

1. **Collect PRs** using GitHub search:
   - Query: `is:pr created:<start_date>..<end_date>`
   - Add `repo:<owner/repo>` if provided
   - Fetch:
     `number`, `title`, `state`, `draft`, `created_at`, `html_url`, `body`,
     `pull_request.merged_at`, `author.login`

2. **Normalize status**:
   - `merged` if `merged_at != null`
   - `draft` if `draft == true`
   - `open` if `state == open` and not draft
   - `closed-unmerged` if `state == closed` and `merged_at == null`

3. **Group by author** (`author.login`).

4. **Classify PRs per author**:
   - **Features**: capabilities, refactors, new APIs, architecture/performance improvements
   - **Fixes**: bug fixes, dependency updates, CI/tooling/workflow/docs/chore cleanup

5. **Consolidate PRs with the same goal** under one entry per author/category.

6. **Build markdown content** using this structure:

```markdown
### Author: <author-login>

#### Features
**Short heading**
One-to-two sentence description.
- [#123 PR title](https://github.com/org/repo/pull/123)
- [#124 PR title](https://github.com/org/repo/pull/124) *(open)*

#### Fixes
**Short heading**
One sentence description.
- [#125 PR title](https://github.com/org/repo/pull/125)
```

Rules:
- For each author, keep this exact order:
  - `### Author: ...`
  - `#### Features`
  - `#### Fixes`
- If one category is empty, keep the heading and add `- None`.
- Mark non-merged PRs with `*(open)*`, `*(draft)*`, or `*(closed-unmerged)*`.
- No emojis.

## Notion requirements (strict)

1. Create the page under:
   - **`Rhesis Gmbh- HQ / meetings`**

2. Create the sprint page using this template:
   - **`Sprint Review # @Today`**

3. Insert the generated author/features/fixes markdown under the template section:
   - **`Delivered`**
   - Keep all other template sections unchanged.

4. If `Delivered` is missing, create it and place the generated content there.

## Output

Return:
- Notion page URL
- Date range used
- Total authors
- Total PRs
- Per-author counts (Features vs Fixes)

If no PRs are found, still create/update the Notion page and place:
`No PRs found for this range.`
