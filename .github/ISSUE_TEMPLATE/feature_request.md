---
name: "✨ Feature Request"
about: Propose a new feature or improvement for Rhesis AI
title: "[Feature] <concise title>"
labels: ["feature", "needs-triage"]
---

<!-- Keep sections crisp. Delete notes you don’t need. -->

## Summary
<!-- 1–2 sentences max. What are we adding and why now? -->
Example: Add a "Run in Playground" button to code snippets so users can test examples instantly.

## Problem / Opportunity
<!-- What user or business problem are we solving? Evidence welcome (tickets, user quotes, data). -->
Example: Users copy/paste code into their editor to test, which interrupts flow and causes errors.

## Users & Use Cases
<!-- Who is this for? Primary workflow(s) in bullets. -->
Example:
- Persona: ML engineers using the Rhesis AI SDK
- Use case: Quickly verify snippet output without leaving docs.

## Proposal
<!-- What should happen? Scope the MVP. Add screenshots/mockups if relevant. -->
Example: Add a button under each code block that opens an interactive editor with the snippet pre-loaded.

### User Story (optional)
<!-- As a <user>, I want <capability>, so that <value>. -->
Example: As a developer, I want to run samples inline so I can validate them without switching tools.

### Non-Goals / Out of Scope
<!-- Call out what we are NOT doing to avoid scope creep. -->
Example: No syntax-highlighting changes in this release.

## Acceptance Criteria (testable)
Example:
- [ ] Button appears under all code snippets in docs.
- [ ] Clicking opens the playground with the snippet pre-loaded.
- [ ] Works for Python/JS examples without manual edits.

<details>
<summary>Gherkin (optional)</summary>

```gherkin
Given a docs page with a code snippet
When I click "Run in Playground"
Then the playground opens with the snippet preloaded
And I can execute it successfully
