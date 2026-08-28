---
name: update-branch
description: Rebase a feature branch onto main and force-push it safely. Use when updating, rebasing, or syncing a branch with main, or resolving rebase conflicts.
---

# Updating a Branch

**Rebase onto `main`; don't merge `main` into the branch.**

```bash
git fetch origin && git rebase origin/main
```

Merging leaves a merge commit and interleaves unrelated `main` changes into the branch's history,
which makes the PR diff noisy and stops the branch's own commits from reading as a clean sequence.

## Conflicts

Fix the files, `git add <file>`, then `git rebase --continue`. `git rebase --abort` puts the branch
back the way it was.

## Pushing after a rebase

A rebase rewrites history, so an already-pushed branch needs:

```bash
git push --force-with-lease
```

`--force-with-lease` refuses to overwrite commits someone else pushed, which plain `--force` will
do. On a branch someone else is working on, tell them before you force-push.

**Never force-push `main`.**

Pushing needs the user's go-ahead — see the commit rules in `AGENTS.md`.
