---
name: "Task"
about: Track a piece of work that is not a bug or new feature
title: "<concise title>"
type: "Task"
---

<!-- Keep sections crisp. Delete notes you don’t need. -->

## Summary
<!-- 1–2 sentences max. What is this task about? -->
Example: Update README to include new installation instructions for v1.5.

## Background / Context
<!-- Why is this task needed? Link related issues, PRs, or docs. -->
Example: The setup process changed after we switched to Yarn; README still shows outdated npm commands.

## Goals
<!-- What are we trying to achieve? -->
Example:
- Ensure README matches the current installation process.
- Reduce setup errors for new contributors.

## Deliverables
<!-- Tangible outputs expected from this task. -->
Example:
- Updated README file in root directory.
- Verified that all commands work in Mac, Linux, and Windows.

## Steps / Action Plan
<!-- List the steps to complete the task. -->
Example:
1. Review current README content.
2. Update installation section with Yarn commands.
3. Test on all supported OS.
4. Commit changes and open PR.

## Acceptance Criteria (testable)
Example:
- [ ] README includes Yarn install steps.
- [ ] Instructions verified on Mac, Linux, Windows.
- [ ] No references to outdated npm commands.

## Dependencies
<!-- Anything that must happen before this task can be completed. -->
Example: Wait for v1.5 release to finalize commands.

## Risks / Considerations
<!-- What could block this task or cause rework? -->
Example: Future CLI changes could require another update soon.

## Additional Context
Example: Related to [Issue #456] and [Changelog for v1.5].
