# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.3] - 2025-11-17

### Fixed

- Fixed a bug that caused the frontend Docker image to fail during local deployment.
- Fixed a file ownership issue (chown bug) that could prevent the application from running correctly.

## [0.4.2] - 2025-11-13

### Added

- Added single-step MCP import workflow.
- Added MCP integration for Notion import in the knowledge page.
- Added tags and comments columns to sources grid and source detail page.
- Added Test Set Type field to test sets, displayed in frontend views.
- Added metric scope functionality for single-turn and multi-turn metrics.
- Added local development setup with Docker Compose and auto-login feature.
- Added RocketLaunchIcon to LandingPage for Local Mode display.
- Added test type column and multi-turn goal display in test set detail grid.
- Added multi-turn test configuration UI, integrated into the test detail page.

### Changed

- Simplified MCP import workflow to a single-step process.
- Improved MCP import UX and fixed theme violations.
- Improved multi-turn test UI components and metrics display.
- Enhanced metrics tab with visual indicators and collapsible sections.
- Replaced metric scope multi-select with intuitive selectable chips.
- Updated tests grid to show test type and multi-turn goal.
- Improved test type visual distinction in tests grid.
- Replaced slider with number input for max turns in multi-turn test configuration.
- Updated test title to show goal for multi-turn tests.
- Improved grid layout in knowledge page with flexible columns.

### Fixed

- Improved multi-turn test metrics serialization and frontend display.
- Corrected multi-turn test review display and conflict detection.
- Resolved TypeScript errors in TestsTableView and other frontend components.
- Fixed various PR checker issues and added comprehensive tests.
- Fixed display of metrics for multi-turn tests in test run detail view.
- Resolved ESLint warnings in metrics frontend components.
- Prevented button overlap on single-line fields (Max. Turns).
- Fixed TypeScript linting errors in TestDetailData.
- Fixed theme styles and spacing consistency.
- Allowed detail page access for both rhesis and custom metrics.

### Removed

- Removed Microsoft and Apple login options.
- Removed redundant Score Type label in metric detail view and new metric creation page.
- Removed local development configuration files.
- Removed placeholder goal banner.

## [0.4.1] - 2025-10-30

### Added

- Added support for additional file formats (.pptx, .xlsx, .html, .htm, .zip) for source uploads.
- Added drag-and-drop file upload component for sources.
- Added source indicators to test and test set grids.
- Added context sources to test generation and display in test samples.
- Added project selector to test input screen.
- Added a warning notification when content extraction fails during source upload.
- Added Error status display for test results without metrics.
- Added a re-run button to the test run detail page.
- Added reviews tab to split view and conflict indicators for test runs.
- Added creator information to test sets.
- Added quick search with OData filtering to the test runs grid.
- Added partial status and execution error indicators to test runs.
- Implemented global 404 and 410 error handling with restore functionality.
- Integrated OpenTelemetry for enhanced monitoring.
- Added local deployment models and providers.

### Changed

- Replaced 'Document' terminology with 'Source' throughout the frontend.
- Replaced ContextPreview with a document icon in grids.
- Improved source display in test and test-set pages.
- Updated test generation to use sources instead of documents.
- Updated Rhesis model naming and descriptions.
- Improved AI-based test generation with improved UI and backend support.
- Enhanced hashing mechanism in telemetry for user and organization IDs.
- Updated schemas and initial data for metrics.
- Improved BaseDataGrid quick filter using an uncontrolled input.
- Updated Rhesis Managed badge styling.
- Improved test template usage and flows between screens.
- Made default model indicators more subtle.
- Implemented full editing functionality for knowledge sources.
- Updated test generation to allow an optional test set name parameter.

### Fixed

- Fixed missing ContentCopyIcon import.
- Fixed exhaustive-deps warnings in the `useComments` hook.
- Fixed source name display in confirmation and interface screens for test generation.
- Fixed upload endpoint URL for sources.
- Fixed API key requirement for local deployments.
- Fixed merge conflicts.
- Fixed hardcoded styles.
- Fixed misleading loading state in source preview.
- Fixed 'Name' to 'Title' in source detail.
- Fixed TypeScript error with Chip icon prop in TestRunsGrid.
- Fixed incorrect status color for completed test runs.
- Fixed display of execution time for failed and partial test runs.
- Fixed error breadcrumbs to be reactive to navigation changes.
- Fixed issue where the execute button was enabled when a test set had 0 tests.
- Fixed issue where test results chart had a hardcoded limit of 5 runs.
- Fixed issue where organisation name overlapped.

### Removed

- Removed unused documents section and DescriptionIcon import.
- Removed unused documents state and import.
- Removed undefined documents reference from TestConfigurationConfirmation.
- Removed remaining document references from test generation components.
- Removed scenarios from test templates config and test generation flow.
- Removed the 'rhesis' provider from the user-selectable provider list.
- Removed automatic content extraction during source upload.
- Removed telemetry settings and related components.
- Removed binary score type from new metrics page and metrics detail page.
- Removed import button from manual test writer.

## [0.4.0] - 2025-10-16

### Added

- Implemented Knowledge section with source upload functionality, OData filtering for sources grid, and enhanced source preview with content block design and uploader information display.
- Added comments column to SourcesGrid.
- Implemented user settings API client and interfaces.
- Added conditional endpoint field for self-hosted model providers.
- Added test connection button to model dialog.
- Added friendly error messages with expandable technical details.
- Added validation for website, logo URL, email, and phone fields in organization settings.
- Implemented leave organization feature.
- Added editable test set title functionality.
- Added advanced filtering for test results in test runs.
- Added review management methods to API client.
- Added 'Conflicting Review' filter option.
- Added Tasks & Comments tab to test detail panel.
- Implemented reusable StatusChip component for consistent status display.

### Changed

- Standardized delete button styling across the entire platform.
- Standardized date format to DD/MM/YYYY across knowledge components.
- Moved Knowledge section to appear after Projects in the navigation.
- Improved Knowledge components to match the test-sets pattern.
- Refactored integrations menu to display Models first.
- Renamed "llm-providers" to "models" for consistency.
- Redesigned test runs detail page with a modern dashboard interface.
- Refactored test detail charts with dynamic data and enhanced UI.
- Improved API key field UX and reduced card width.
- Updated model cards to match metrics styling and apply consistent width constraints.
- Applied consistent width constraints to Applications and Tools pages.
- Constrained models page width to match metrics styling.
- Extended DeleteModal with word confirmation, optional top border, bold text support, and simplified DangerZone.
- Improved status card layout and typography in TestRunHeader.
- Improved comparison view layout and real-time comment updates.
- Simplified Review column in table view to a dual-icon system.

### Fixed

- Resolved blank file downloads in the knowledge section.
- Resolved code formatting issues.
- Resolved infinite loop in SourcesGrid component.
- Updated params type for Next.js 15 compatibility.
- Resolved hydration mismatch in date formatting.
- Resolved infinite loading in tasks section.
- Resolved flickering data grid on test runs page.
- Resolved duplicate import ESLint error in TokensGrid.
- Improved token deletion confirmation message.
- Aligned token empty state with theme.
- Resolved user deletion 500 error.
- Prevented automatic headers from being stored in request_headers.
- Prevented button text flicker when closing dialog and in edit mode.
- Properly cleared default model settings when toggling off.
- Improved disabled button visibility and added connection test requirement alerts.
- Corrected machine icon to show original automated result.
- Resolved TypeScript errors and linting issues.
- Fixed hardcoded style violations and replaced them with theme values.
- Fixed Prettier formatting issues.
- Fixed hardcoded styles in DangerZone.
- Fixed hardcoded style values to comply with theme standards.
- Fixed hardcoded font sizes with theme values.
- Fixed hardcoded values with theme tokens.
- Fixed theme borderRadius instead of hard-coded values.
- Fixed Prettier formatting in TasksSection.
- Fixed escape apostrophes in DomainSettingsForm text.
- Fixed: always send endpoint field in test connection request.
- Fixed: preserve natural error messages from all providers in connection test.
- Fixed: fetch all provider types by adding limit parameter.
- Fixed: remove server-side console.logs causing hydration errors.
- Fixed: actually pass additionalMetadata when creating tasks.
- Fixed: correct entity type for tasks created from test results.
- Fixed: improve token deletion confirmation message.

### Removed

- Removed all comment functionality from sources.
- Removed back and copy buttons from source preview header.
- Removed formatted/raw toggle from source preview.
- Removed white container wrapper from source preview.
- Removed header section from Knowledge page.
- Removed file type icons from SourcesGrid title column.
- Removed editor settings from user settings.
- Removed subscription section from organization settings.
- Removed domain settings from organization settings page.
- Removed redundant View Details action.
- Removed redundant test count display.
- Removed step prefix from evaluation steps edit fields.

## [0.3.0] - 2025-10-02

### Added

- Implemented comprehensive frontend testing infrastructure with Jest and React Testing Library.
- Added pre-commit hooks for code formatting and linting.
- Added comments and tasks count columns to entity DataGrids.
- Implemented server-side search for test set selection.
- Added editable task title with validation.
- **Complete rebranding**: Introduced new Rhesis AI logos, color palette, and visual design system.
- Added a demo route with Auth0 login_hint integration.
- Added theme-based circular border radius support.
- Added complete versioning information for backend and frontend.

### Changed

- **Complete application rebranding**: Updated entire application with new Rhesis AI theme, fonts, color palette, and brand elements.
- Redesigned the demo page with a professional UI and brand elements.
- Enhanced task detail page with navigation button and improved UI consistency.
- Standardized avatar sizes and consolidated task details UI.
- Improved metric card chips and UI behavior.
- Improved test results interface clarity.
- Truncated project description after 250 characters in ProjectCard.
- Optimized chart space utilization and fixed alignment issues.
- Improved visual consistency across onboarding components.
- Updated logo to increased platypus variant with dark mode support.
- Reduced default sidebar width.
- Standardized font sizes and added typography variants to the theme.

### Fixed

- Resolved duplicate key error in Run Test Drawer with same project names.
- Resolved initial load issue and improved error handling for tasks.
- Resolved task details page error.
- Resolved TypeScript error in TestSetSelectionDialog useRef initialization.
- Improved error handling and prevented flickering in task components.
- Resolved GitHub Actions testing issues.
- Resolved React 19 compatibility issues in GitHub Actions.
- Fixed hardcoded styles and validation issues across various components.
- Fixed inconsistencies in chip colors and elevation issues.
- Prevented charts from reloading on tab focus.
- Standardized layout consistency and axis visibility across all chart components.
- Improved endpoints detail page design consistency.
- Corrected elevation prop usage to use numeric values.

### Removed

- Removed redundant Final_Summary.md and testing documentation files.
- Removed workflow section from metrics, test-sets, and test-runs pages.
- Removed reports navigation item.

## [0.2.4] - 2025-09-18

### Added

- Added "Source Documents" section to individual Test Detail page, displaying associated documents.
- Added "Source Documents" section to Test Set Details page, displaying associated documents.
- Added document, name, and description fields to the Test Set interface.
- Added `test_metadata` field to the `TestBase` interface.
- Added a send button to the comment text box.

### Changed

- Updated project title and description to update reactively upon editing, without requiring a page reload.
- Updated breadcrumb and title in the test header to display content instead of UUID.
- Improved test coverage.

### Fixed

- Ensured compatibility between comment and token frontend interfaces and the backend.
- Fixed test stepper return behavior.

## [0.2.3] - 2025-09-04

### Added

- Added dynamic charts for test run details.
- Added comments feature for collaboration on tests, test sets, and test runs.
- Added error boundary for improved application stability.
- Added loading spinners to metrics creation and deletion processes.

### Changed

- Improved performance of the test run stats endpoint.
- Optimized API client interfaces and behavior client methods.
- Refactored metrics functionality into separate components for better maintainability.
- Improved environment variable handling for local development and deployment flexibility.
- Updated Dockerfile for enhanced build process and environment configuration.

### Fixed

- Fixed tooltip visibility issues across different themes.
- Fixed display issues with tooltips for test runs.
- Fixed TypeScript warnings.
- Fixed flickering issue in the test run datagrid.
- Eliminated unnecessary re-renders in the metrics detail page.
- Fixed inconsistencies and re-renders during metric editing.
- Resolved issues with multiple API calls during metric editing.
- Fixed display of metrics confirmation page during creation.
- Fixed issue where metrics not associated with behaviors were not displayed.
- Fixed macOS IPv6 localhost connection issues.

## [0.2.2] - 2025-08-22

### Added

- Added document upload step with automatic metadata generation.
- Added support for Central European, Nordic, and Eastern European characters in BaseTag validation.
- Updated frontend supported file extensions to match SDK.

### Changed

- Refactored docker-compose and environment configuration.
- Improved migration and start up scripts for docker backend.
- Adjusted frontend Dockerfile to production mode.
- Updated Complete Setup button behavior after successful onboarding.
- Changed 'Generated Name' and 'Generated Description' to just 'Name' and 'Description' in the frontend.
- Updated supported file extensions for document upload.

### Fixed

- Fixed issue where projects were not automatically refreshing after new project creation.
- Fixed issue where long project names were truncated.
- Fixed various issues in the document generation configuration flow, including:
  - State persistence.
  - Inconsistent button behavior.
  - Test coverage labels.
  - Button label and description.
  - Field label naming.
  - Behaviors and topics display in the final step.
  - File size validation.
  - Next button validation on the first step.
- Fixed `handleNext` double step increment bug.
- Improved document metadata extraction using a structured prompt format.
- Fixed document upload state updates.

### Removed

- Removed projects-legacy and unnecessary navigation items.
- Removed unnecessary refresh button.
- Removed unsupported file extensions (.url, .youtube).

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
