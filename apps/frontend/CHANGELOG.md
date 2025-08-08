# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2025-08-08

### Added
- Introduced Test Results functionality, allowing users to view and analyze test outcomes.
- Added interfaces for handling test results statistics.

### Fixed
- Resolved an issue causing infinite loading for test sets.

### Changed
- Updated contributing guides to reflect new PR creation and update features.


## [0.2.0] - 2025-07-25

### Added
- Display of frontend version information in the application.
- Environment variables are now accessible to the client-side application.
- Functionality to add users outside of the onboarding flow.
- Introduced a team invitation stepper with email uniqueness check, proper email validation, rate limiting (10 invites/hour), and max team size (10).
- Download button added to the test run view.
- Added snack bar notification to test set execution.

### Changed
- Improved team invitation security and validation.
- Enhanced error handling and duplicate detection in team invitation.
- Improved BasePieChart legend position.
- Updated dependencies: `form-data` from 4.0.1 to 4.0.4.
- Adjusted total prompts to total tests throughout the frontend.
- Improved generation of test cases.
- Improved and refactored task orchestration.
- Made run time display more user-friendly.
- Improved contrast in dark mode.

### Fixed
- Prevented email addresses from being used as first names during onboarding.
- Fixed duplicate identifier issues in BaseDataGrid.
- Fixed contrast issues in dark mode.
- Ensured server logout upon session expiration.
- Cleared validation errors for the frontend.
- Hardened application logout and synchronized backend/frontend logout.
- Fixed chips display for test sets and other entities.
- Test set execution via test run list is now functional again.
- Fixed session length issues in the backend/frontend.
- Fixed test set pagination.
- Fixed missing expected response in reliability prompts.
- Fixed the display of behaviors in the context of test runs.
- Fixed execution time display for progress test runs.
- Fixed test run data grid header.
- Fixed total tests display for test runs.
- Fixed endpoint creation notification.
- Fixed new endpoint page.
- Fixed race condition when displaying endpoint.
- Fixed adjusting total_tests display in runs data grid.
- Fixed not showing notification when adding tests to testset.
- Fixed application and endpoint selection not showing values.
- Fixed the testset selection field name as key instead of id as key issue.
- Fixed completion timestamp and endpoint fields.
- Fixed issue with styling in LLM provider overview (grid).
- Replaced empty columns in test run grid.
- Fixed unescaped strings.
- Fixed Windows-type authentication.


## [0.1.0] - 2025-05-15

### Added
- Initial release of the frontend application
- Next.js 15 with App Router implementation
- Material UI v6 component library integration
- Authentication system with NextAuth.js
- Protected routes and middleware
- Dashboard with test management interface
- Projects management screens
- Test sets and test cases visualization
- Test runs monitoring
- API client integration with backend services
- Dark/light theme support
- Responsive design for desktop and mobile
- User onboarding flow
- Organization management

### Note
- This component is part of the repository-wide v0.1.0 release
- After this initial release, the frontend will follow its own versioning lifecycle with frontend-vX.Y.Z tags

[Unreleased]: https://github.com/rhesis-ai/rhesis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/v0.1.0 