# Table View Implementation

## Overview

A new table-based view for displaying test results has been added to the test run detail page. Users can now toggle between the original split view (master-detail layout) and a new table view.

## Components Created

### 1. TestsTableView.tsx

Main table view component that displays test results in a tabular format.

**Features:**

- **Three columns:**
  - **Prompt**: Shows truncated prompt text with full content in tooltip
  - **Response**: Shows truncated response text with full content in tooltip
  - **Evaluation**: Displays pass/fail status with metric counts and failed metric names
  - **Actions**: Dropdown menu with actions

- **Interactive features:**
  - Click any row to open detail drawer
  - Hover effects on rows
  - Pagination support (10, 25, 50, 100 rows per page)
  - Action menu with:
    - View Details
    - Overrule Judgement (placeholder for future implementation)

- **Detail Drawer:**
  - Slides in from the right
  - Shows full TestDetailPanel component
  - Responsive width (60-100% depending on screen size)
  - Close button in header

## Modified Components

### 2. TestRunMainView.tsx

Updated to support view mode switching.

**Changes:**

- Added `viewMode` state ('split' | 'table')
- Conditional rendering based on viewMode
- Passes viewMode props to TestRunFilterBar
- Renders either split layout or TestsTableView based on mode

### 3. TestRunFilterBar.tsx

Enhanced with view mode toggle buttons.

**Changes:**

- Added `viewMode` and `onViewModeChange` props
- New ButtonGroup with two options:
  - Split view (icon: ViewColumn)
  - Table view (icon: TableRows)
- Positioned between filters and action buttons

## Usage

The view mode toggle is automatically available in the filter bar:

```tsx
// Users can switch views using the toggle buttons
[Split][Table] | Compare | Download;
```

### Split View (Default)

- Left panel (33%): Scrollable list of test cards
- Right panel (67%): Full test detail panel with tabs
- Best for deep investigation of individual tests

### Table View

- Full-width table with all tests
- Compact view showing key information
- Quick scanning of multiple tests
- Click any row to open detail drawer
- Best for overview and batch operations

## Future Enhancements

### Overrule Judgement Action

Currently shows a placeholder console.log. This should be implemented to:

1. Open a dialog/modal for justification
2. Call API to update test result status
3. Show audit trail of overruled judgements
4. Require user permissions/role check

### Additional Actions

Consider adding to the action menu:

- Add comment
- Create task
- Mark as false positive
- Export single test
- Copy test details

### Table Enhancements

- Column sorting
- Column visibility toggle
- Resize columns
- Sticky columns
- Bulk selection with multi-actions
- Export selected tests
- Apply tags to multiple tests

## Technical Details

### Props Interface

```typescript
interface TestsTableViewProps {
  tests: TestResultDetail[];
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  testRunId: string;
  sessionToken: string;
  loading?: boolean;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}
```

### State Management

- Local pagination state
- Selected test for drawer
- Drawer open/close state
- Action menu anchor element

### Performance Considerations

- Pagination to handle large datasets (default 25 rows)
- Truncated text display (150 chars) to prevent row height issues
- Tooltips for full content on hover
- Virtualization can be added for 1000+ tests

## Styling

- Consistent with existing MUI theme
- Hover states with primary color alpha
- Selected row highlighting
- Responsive drawer width
- Sticky table header

## Accessibility

- Keyboard navigation supported
- Hover tooltips with proper delays
- ARIA labels on interactive elements
- Screen reader compatible table structure
