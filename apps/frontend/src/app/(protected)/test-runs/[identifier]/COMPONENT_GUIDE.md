# Test Runs Component Architecture Guide

## Component Hierarchy

```
page.tsx (Server Component)
└── PageContainer (Toolpad)
    ├── TestRunHeader
    │   └── 4x SummaryCard (Grid)
    │
    ├── TestRunDetailCharts (kept from old design)
    │   └── Charts (Recharts)
    │
    ├── TestRunMainView (Client Component - Main Container)
    │   ├── TestRunFilterBar
    │   │   ├── Search TextField
    │   │   ├── Status ButtonGroup (All/Passed/Failed)
    │   │   ├── Behavior Filter Popover
    │   │   └── Download Button
    │   │
    │   └── Grid (Split Layout)
    │       ├── TestsList (40% width)
    │       │   └── List of TestListItem
    │       │       ├── Status Icon
    │       │       ├── Prompt Preview
    │       │       └── Metrics Chips
    │       │
    │       └── TestDetailPanel (60% width)
    │           ├── Tabs Navigation
    │           └── Tab Content
    │               ├── TestDetailOverviewTab
    │               │   ├── Status Chip
    │               │   ├── Prompt Section
    │               │   ├── Response Section
    │               │   └── Behavior Accordions
    │               │
    │               ├── TestDetailMetricsTab
    │               │   ├── 3x Summary Cards
    │               │   ├── Toggle Filter
    │               │   └── Metrics Table
    │               │
    │               └── TestDetailHistoryTab
    │                   ├── History Table
    │                   └── Summary Statistics
    │
    └── TasksAndCommentsWrapper (kept from old design)
```

## Component Props Reference

### TestRunHeader

```typescript
{
  testRun: TestRunDetail;           // Test run metadata
  testResults: TestResultDetail[];  // All test results for stats
  loading?: boolean;                // Optional loading state
}
```

### TestRunFilterBar

```typescript
{
  filter: FilterState;                      // Current filter state
  onFilterChange: (filter: FilterState) => void;  // Filter callback
  availableBehaviors: Behavior[];           // For behavior filter
  onDownload: () => void;                   // Download handler
  isDownloading?: boolean;                  // Download state
  totalTests: number;                       // Total test count
  filteredTests: number;                    // Filtered count
}
```

### TestsList

```typescript
{
  tests: TestResultDetail[];        // Tests to display
  selectedTestId: string | null;    // Currently selected test
  onTestSelect: (id: string) => void;  // Selection handler
  loading?: boolean;                // Loading state
  prompts: Record<string, Prompt>;  // Prompt lookup map
}
```

### TestDetailPanel

```typescript
{
  test: TestResultDetail | null;    // Selected test (null = none)
  loading?: boolean;                // Loading state
  prompts: Record<string, Prompt>;  // Prompt lookup
  behaviors: BehaviorWithMetrics[]; // Behaviors with metrics
  testRunId: string;                // For history fetching
  sessionToken: string;             // For API calls
}
```

### TestRunMainView

```typescript
{
  testRunId: string;                // Test run identifier
  sessionToken: string;             // Auth token
  testResults: TestResultDetail[];  // All results
  prompts: Record<string, Prompt>;  // Prompt map
  behaviors: BehaviorWithMetrics[]; // Behaviors with metrics
  loading?: boolean;                // Loading state
}
```

## State Management

### TestRunMainView State

```typescript
// Test selection
const [selectedTestId, setSelectedTestId] = useState<string | null>(null);

// Download state
const [isDownloading, setIsDownloading] = useState(false);

// Filter state
const [filter, setFilter] = useState<FilterState>({
  searchQuery: '',
  statusFilter: 'all',
  selectedBehaviors: [],
});
```

### TestDetailPanel State

```typescript
const [activeTab, setActiveTab] = useState(0); // 0=Overview, 1=Metrics, 2=History
```

### TestDetailHistoryTab State

```typescript
const [history, setHistory] = useState<HistoricalResult[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

## Data Flow

### Server → Client

```
page.tsx (Server)
  ↓ Fetches test run, results, prompts, behaviors
  ↓ Passes as props
TestRunMainView (Client)
  ↓ Manages filtering and selection
  ↓ Passes filtered data
TestsList & TestDetailPanel
  ↓ Renders UI
```

### User Interactions

```
User types in search
  ↓ TestRunFilterBar onChange
  ↓ TestRunMainView updates filter state
  ↓ useMemo recalculates filteredTests
  ↓ TestsList re-renders with filtered data

User clicks test in list
  ↓ TestsList onTestSelect
  ↓ TestRunMainView updates selectedTestId
  ↓ TestDetailPanel re-renders with new test
```

## Styling Patterns

### Card Pattern

```typescript
<Card
  sx={{
    transition: 'transform 0.2s, box-shadow 0.2s',
    '&:hover': {
      transform: 'translateY(-2px)',
      boxShadow: theme.shadows[4],
    },
  }}
>
```

### Scrollable Container Pattern

```typescript
<Box
  sx={{
    height: '100%',
    overflow: 'auto',
    '&::-webkit-scrollbar': {
      width: '8px',
    },
    '&::-webkit-scrollbar-track': {
      background: theme.palette.background.default,
      borderRadius: '4px',
    },
    '&::-webkit-scrollbar-thumb': {
      background: theme.palette.divider,
      borderRadius: '4px',
      '&:hover': {
        background: theme.palette.action.hover,
      },
    },
  }}
>
```

### Status Chip Pattern

```typescript
<Chip
  icon={isPassed ? <CheckCircleIcon /> : <CancelIcon />}
  label={isPassed ? 'Passed' : 'Failed'}
  size="small"
  color={isPassed ? 'success' : 'error'}
  sx={{ fontWeight: 600 }}
/>
```

## Common Calculations

### Test Pass/Fail Status

```typescript
const metrics = test.test_metrics?.metrics || {};
const metricValues = Object.values(metrics);
const totalMetrics = metricValues.length;
const passedMetrics = metricValues.filter(m => m.is_successful).length;
const isPassed = totalMetrics > 0 && passedMetrics === totalMetrics;
```

### Pass Rate

```typescript
const total = testResults.length;
const passed = testResults.filter(r => {
  const metrics = r.test_metrics?.metrics;
  if (!metrics) return false;
  return Object.values(metrics).every(m => m.is_successful);
}).length;
const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0.0';
```

### Duration Calculation

```typescript
const startedAt = testRun.attributes?.started_at;
const completedAt = testRun.attributes?.completed_at;
if (startedAt && completedAt) {
  const diffMs =
    new Date(completedAt).getTime() - new Date(startedAt).getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffSecs = Math.floor((diffMs % 60000) / 1000);
  duration = `${diffMins}m ${diffSecs}s`;
}
```

## Responsive Breakpoints

```typescript
// Mobile First
xs: 0,      // 0px+
sm: 600,    // 600px+
md: 900,    // 900px+
lg: 1200,   // 1200px+
xl: 1536,   // 1536px+

// Usage in Grid
<Grid item xs={12} sm={6} md={3}>  // Full on mobile, half on tablet, quarter on desktop
<Grid item xs={12} md={5}>         // Full on mobile, 40% on desktop
<Grid item xs={12} md={7}>         // Full on mobile, 60% on desktop
```

## Performance Tips

### Use useMemo for Expensive Calculations

```typescript
const filteredTests = useMemo(() => {
  // Expensive filtering logic
}, [testResults, filter, prompts, behaviors]);
```

### Use useCallback for Event Handlers

```typescript
const handleTestSelect = useCallback((testId: string) => {
  setSelectedTestId(testId);
}, []);
```

### Avoid Prop Drilling

- Keep state as close to where it's used as possible
- Pass only necessary data down
- Use composition over deep nesting

## Debugging Tips

### Check Test Results Structure

```typescript
console.log('Test Results:', testResults);
console.log('First Result:', testResults[0]);
console.log('Metrics:', testResults[0]?.test_metrics?.metrics);
```

### Verify Filter Logic

```typescript
console.log('Filter State:', filter);
console.log('Filtered Tests:', filteredTests);
console.log('Filter Count:', filteredTests.length, '/', testResults.length);
```

### Monitor Re-renders

```typescript
useEffect(() => {
  console.log('Component rendered with:', { test, selectedTestId });
}, [test, selectedTestId]);
```

## Common Issues & Solutions

### Issue: Selected test not showing

**Solution**: Check if `selectedTestId` matches any test ID in `testResults`

### Issue: Filters not working

**Solution**: Verify filter logic in `filteredTests` useMemo

### Issue: Metrics not displaying

**Solution**: Check that behaviors have metrics loaded

### Issue: History not loading

**Solution**: Verify `test.test_id` exists and API token is valid

### Issue: Layout breaks on mobile

**Solution**: Check Grid `xs` breakpoint props

## Future Enhancements

1. **Virtual Scrolling**: For 1000+ tests
2. **Test Comparison**: Side-by-side view
3. **Per-Test Comments**: Backend entity relationships needed
4. **Export Individual Tests**: CSV/JSON export
5. **Keyboard Shortcuts**: J/K navigation, ESC to clear selection
6. **Test Bookmarking**: Save favorite tests
7. **Advanced Filters**: Regex search, metric-specific filters
8. **Trend Charts**: Historical performance graphs
9. **Real-time Updates**: WebSocket for live test results
10. **Bulk Actions**: Select multiple tests for operations
