## PR Changelog -- akwasigroch (2026-04-27 -- 2026-05-11)

### Features

**Test Explorer naming, navigation, and docs**

Aligned the adaptive-testing UI with Explorer product naming, sidebar placement, and user-facing flows, then added a dedicated documentation set covering the overview, workflow, building and evaluating, and scenarios.

- [#1726](https://github.com/rhesis-ai/rhesis/pull/1726)
- [#1714](https://github.com/rhesis-ai/rhesis/pull/1714)

**Runtime-configurable frontend connections**

Moved frontend API and websocket endpoint resolution toward runtime and server-owned configuration so preview, local, and promoted images can point at different backends without rebuilding. The remaining open work covers container-start placeholder substitution and Cloud Run environment wiring.

- [#1707](https://github.com/rhesis-ai/rhesis/pull/1707) *(open)*
- [#1690](https://github.com/rhesis-ai/rhesis/pull/1690) *(open)*

**Lean backend dependency and image paths**

Split backend dependencies into a lean core plus optional heavy extras, made package install and sync commands consume the intended extras, and removed unnecessary Rust tooling from Polyphemus image builds.

- [#1689](https://github.com/rhesis-ai/rhesis/pull/1689)
- [#1687](https://github.com/rhesis-ai/rhesis/pull/1687)
- [#1686](https://github.com/rhesis-ai/rhesis/pull/1686)

### Fixes

**Adaptive Testing delete response**

Fixed Explorer and Adaptive Testing test-set deletion to return the expected response payload after delete operations.

- [#1730](https://github.com/rhesis-ai/rhesis/pull/1730)

**GHCR and deployment workflow hardening**

Reworked GHCR build workflows, backend image publishing, and monorepo Docker paths to unblock package publishing, parallelize backend and migration image builds, and support prebuilt quickstart images.

- [#1706](https://github.com/rhesis-ai/rhesis/pull/1706) *(open)*
- [#1702](https://github.com/rhesis-ai/rhesis/pull/1702)
- [#1701](https://github.com/rhesis-ai/rhesis/pull/1701)
- [#1698](https://github.com/rhesis-ai/rhesis/pull/1698)
- [#1692](https://github.com/rhesis-ai/rhesis/pull/1692)

**CI dependency and documentation maintenance**

Updated GitHub Actions dependencies, package constraints, and kubectl logging documentation syntax to keep build and operations tooling current.

- [#1700](https://github.com/rhesis-ai/rhesis/pull/1700)
- [#1699](https://github.com/rhesis-ai/rhesis/pull/1699)
- [#1693](https://github.com/rhesis-ai/rhesis/pull/1693)
- [#1688](https://github.com/rhesis-ai/rhesis/pull/1688)
