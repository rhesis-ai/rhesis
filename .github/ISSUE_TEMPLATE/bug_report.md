---
name: "Bug Report"
about: Report something that isn't working as expected in Rhesis AI
title: "[Bug] <concise title>"
labels: ["bug", "needs-triage"]

---

<!-- Keep sections crisp. Delete notes you don’t need. -->

## Summary
<!-- 1–2 sentences max. What’s wrong? -->
Example: The "Run in Playground" button fails to load the snippet when clicked from the docs site.

## Steps to Reproduce
<!-- Exact, numbered steps so someone else can trigger the bug. -->
Example:
1. Go to https://www.rhesis.ai
2. Navigate to any code example page
3. Click the "Run in Playground" button
4. Observe: Playground loads blank

## Expected Behavior
<!-- What *should* happen if the bug didn’t exist? -->
Example: Playground should open with the code snippet preloaded.

## Actual Behavior
<!-- What *does* happen instead? -->
Example: Playground loads with no content, console shows `Error: Snippet not found`.

## Screenshots / Recordings
<!-- Add images, GIFs, or videos if relevant. -->
Example: *(Attach screenshot of blank playground and console error)*

## Environment
<span style="color:red">This may be necessary?.</span>

<!-- Include as many as apply. -->
Example:
- Browser: Chrome 128.0.6613.119
- OS: macOS 14.5
- Network: Wi-Fi, stable connection
- Rhesis AI version: 1.4.2

## Logs / Console Output
<!-- Paste any relevant logs or error messages. -->
Example:

## Impact
<!-- How bad is it? -->
Example:
- Frequency: 100% reproduction
- Impact: Blocks all users from testing code snippets via docs.

## Possible Cause (optional)
Example: Might be failing to pass snippet ID to the playground service.

## Acceptance Criteria (testable)
Example:
- [ ] Clicking "Run in Playground" opens the playground with snippet preloaded.
- [ ] Works across Chrome, Firefox, and Safari.
- [ ] No errors in browser console.

## Additional Context
Example: Related to [Feature Request #456] that added the "Run in Playground" button.
