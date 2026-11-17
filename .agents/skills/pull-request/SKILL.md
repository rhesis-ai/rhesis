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
- **The repo is public, so write for any reader.** The title, description, commit messages, code
  comments and review replies say what the change adds and how it was tested, nothing more.
  Leave out:
  - The weakness a change closes, and how it could be abused. Write "Add a size limit to file
    uploads", not "uploads have no size limit, so anyone can fill the disk".
  - Remaining gaps, follow-up risks, and anything not yet fixed.
  - Production details: account, project, cluster and secret names, which credentials have which
    access, infrastructure layout.
  - Business context: launch dates, customers, users, incidents, costs.
  - Ops steps and runbooks (rotate this key, run this command in prod).

  Keep that context in the conversation with the user. Before pushing, reread the description
  and the commit messages with this list in mind. Editing a description later doesn't remove the
  old text: GitHub keeps it in the edit history.
- **Keep the description short.** A few plain bullets. Internals like error codes, which
  endpoints refuse what, or exemptions belong in the code and docs, not the PR.
- Description must include these sections:

  ```markdown
  ## Purpose

  [One or two sentences on what the change adds or fixes, stated neutrally]

  ## What Changed

  - [Key change 1]

  ## Additional Context

  - [Links to issues, tickets, breaking changes]

  ## Testing

  [How to test these changes]
  ```
