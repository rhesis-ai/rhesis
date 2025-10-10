# Test Runs Interface - Visual Overview

## New Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Test Runs > Run #abc123                              [Breadcrumbs]     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  SUMMARY CARDS (4-column responsive grid)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│  │Pass Rate │ │  Tests   │ │ Duration │ │  Status  │                  │
│  │  85.2%   │ │   120    │ │  2m 15s  │ │✓Complete │                  │
│  │ 102/120  │ │102 passed│ │Dec 5,2024│ │TestSet#1 │                  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  CHARTS (Line chart + 3 pie charts)                                     │
│  [Kept from original design - shows test run trends & breakdowns]       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  FILTER BAR                                                              │
│  [🔍 Search...] [All][✓Passed][✗Failed] [📊Filters] 102/120  [⬇Download]│
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┬──────────────────────────────────────────┐
│  TESTS LIST (40%)            │  TEST DETAIL PANEL (60%)                 │
│  ┌──────────────────────────┐│  ┌──────────────────────────────────────┐│
│  │ ✓ Test prompt text...   ││  │ [Overview][Metrics][History]         ││
│  │   [Passed] 8/8 metrics  ││  │                                      ││
│  └──────────────────────────┘│  │ ┌──────────────────────────────────┐││
│  ┌──────────────────────────┐│  │ │ Test Result: ✓ Passed           │││
│  │ ✗ Another test prompt...││  │ └──────────────────────────────────┘││
│  │   [Failed] 5/8 metrics  ││  │                                      ││
│  └──────────────────────────┘│  │ Prompt:                             ││
│  ┌──────────────────────────┐│  │ ┌──────────────────────────────────┐││
│  │ ✓ Third test prompt...  ││  │ │ "What is the capital of France?" │││
│  │   [Passed] 8/8 metrics  ││  │ └──────────────────────────────────┘││
│  └──────────────────────────┘│  │                                      ││
│  │                          ││  │ Response:                            ││
│  │  [Scrollable list]       ││  │ ┌──────────────────────────────────┐││
│  │                          ││  │ │ "The capital of France is Paris."│││
│  │                          ││  │ └──────────────────────────────────┘││
│  │                          ││  │                                      ││
│  │                          ││  │ Behavior Metrics:                    ││
│  │                          ││  │ ▼ ✓ Accuracy (8/8) [Green BG]       ││
│  │                          ││  │   ✓ Metric 1: Result...             ││
│  │                          ││  │   ✓ Metric 2: Result...             ││
│  │                          ││  │ ▼ ✗ Tone (0/2) [Red BG]             ││
│  │                          ││  │   ✗ Metric 3: Result...             ││
│  └──────────────────────────┘│  └──────────────────────────────────────┘│
└──────────────────────────────┴──────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  TASKS & COMMENTS (Test Run Level)                                      │
│  [Kept from original design]                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Visual Features

### 🎨 Color Coding

- **Green** (Success): Pass rates ≥80%, passed tests, passed metrics
- **Red** (Error): Failed tests, failed metrics, pass rates <50%
- **Orange** (Warning): Pass rates 50-79%
- **Blue** (Primary): UI elements, buttons, selected states
- **Gray** (Neutral): Text, borders, disabled states

### ✨ Interactions

#### Hover Effects

```
Cards:          Lift up 2px + shadow increase
Test Items:     Slide right 4px + hover background
Buttons:        Background color change
```

#### Selection States

```
Selected Test:  Blue 2px border + elevation 3 + background highlight
Active Tab:     Blue underline + bold text
Active Filter:  Contained button style + badge
```

#### Loading States

```
Summary Cards:  Skeleton loaders (3 animated bars)
Test List:      5 skeleton items with pulsing animation
Detail Panel:   Full-panel skeleton with structured blocks
```

#### Empty States

```
No Tests:       Icon + "No tests found" message
No Selection:   Large icon + "Select a test" message
No History:     Table with "No historical data" message
```

## Screen Sizes

### Desktop (≥900px)

```
┌───────────────────────────────────────────────┐
│  Cards: 4 columns (25% each)                  │
│  Split: 40% Tests List | 60% Detail Panel     │
│  Height: calc(100vh - 420px)                  │
└───────────────────────────────────────────────┘
```

### Tablet (600-899px)

```
┌────────────────────────────┐
│  Cards: 2 columns (50%)    │
│  Split: Stacked vertically │
│  List: 400px height        │
│  Detail: 600px height      │
└────────────────────────────┘
```

### Mobile (<600px)

```
┌─────────────────┐
│  Cards: 1 col   │
│  Filters: Stack │
│  List: 400px    │
│  Detail: 600px  │
│  All: Full width│
└─────────────────┘
```

## Typography Scale

```
Page Title (Breadcrumb):  h5, Sora Semibold
Card Values:             h4, Be Vietnam Pro Semibold
Card Titles:             body2, Be Vietnam Pro Medium
Tab Labels:              Tab component default
Section Headers:         subtitle2, Be Vietnam Pro Semibold
Body Text:               body2, Be Vietnam Pro Regular
Metric Names:            body2, Be Vietnam Pro Medium
Metric Values:           caption, Monospace
```

## Spacing System

```
Page Padding:        pt: 3 (24px)
Section Gaps:        mb: 4 (32px)
Grid Gaps:           spacing: 3 (24px)
Card Padding:        p: 3 (24px)
List Item Margin:    mb: 1 (8px)
Tab Content Padding: p: 3 (24px)
Button Gaps:         gap: 1 (8px)
Icon Gaps:           gap: 0.5-2 (4-16px)
```

## Icons Used

```
Summary Cards:
  - CheckCircleIcon (Pass Rate)
  - PlayCircleFilledIcon (Tests Executed)
  - TimerIcon (Duration)
  - CheckCircleIcon/CancelIcon (Status)

Filters:
  - SearchIcon (Search)
  - ListIcon (All filter)
  - CheckCircleOutlineIcon (Passed filter)
  - CancelOutlinedIcon (Failed filter)
  - FilterListIcon (Behavior filter)
  - DownloadIcon (Download)

Test List:
  - CheckCircleIcon (Passed test)
  - CancelIcon (Failed test)

Tabs:
  - InfoOutlinedIcon (Overview)
  - AssessmentOutlinedIcon (Metrics)
  - HistoryIcon (History)
  - CommentOutlinedIcon (Comments - future)
  - TaskAltOutlinedIcon (Tasks - future)

Behavior Metrics:
  - ExpandMoreIcon (Accordion)
  - CheckCircleIcon (Passed metric)
  - CancelIcon (Failed metric)
```

## Animation Timings

```
Hover Transitions:     0.2s ease
Card Elevation:        0.2s ease
List Item Slide:       0.2s ease
Tab Switch:            Instant (no animation)
Filter Application:    Instant (immediate re-render)
Skeleton Pulse:        1.5s infinite
```

## Shadows (Elevation)

```
Cards (Default):       elevation={1}  → boxShadow[1]
Cards (Hover):         elevation={4}  → boxShadow[4]
Selected Test:         elevation={3}  → boxShadow[3]
Paper (Containers):    elevation={2}  → boxShadow[2]
Modals/Dialogs:        elevation={8}  → boxShadow[8]
```

## Border Radius

```
Cards:                 12px (theme default)
Chips:                 16px (small: auto)
Buttons:               4px (theme default)
Text Fields:           4px (theme default)
Accordion Items:       4px
Scrollbar Thumb:       4px
```

## Accessibility Features

```
✓ ARIA labels on all interactive elements
✓ Tab navigation fully supported
✓ Focus indicators visible
✓ Color contrast meets WCAG AA
✓ Screen reader text where needed
✓ Semantic HTML structure
✓ Keyboard shortcuts supported
✓ Touch targets ≥44px
```

## Mobile Optimizations

```
✓ Touch-friendly targets
✓ Stacked layouts
✓ Reduced columns
✓ Scrollable containers
✓ Bottom sheet patterns (for filters)
✓ Sticky headers
✓ Pull-to-refresh ready
✓ Responsive images
```

## Browser Support

```
✓ Chrome 90+
✓ Firefox 88+
✓ Safari 14+
✓ Edge 90+
✓ Mobile Safari (iOS 14+)
✓ Chrome Mobile (Android 10+)
```

## Performance Metrics

```
Initial Load:        < 3s (target)
Filter Response:     < 200ms
Search Response:     < 200ms
Tab Switch:          < 100ms
Test Selection:      < 50ms
Scroll Performance:  60fps
```

## Component Sizes

```
TestRunHeader:           ~250 lines
TestRunFilterBar:        ~180 lines
TestsList:               ~180 lines
TestDetailPanel:         ~120 lines
TestDetailOverviewTab:   ~280 lines
TestDetailMetricsTab:    ~220 lines
TestDetailHistoryTab:    ~160 lines
TestRunMainView:         ~180 lines
Total New Code:          ~1,570 lines
```

## Data Flow Visual

```
                    ┌─────────────┐
                    │  page.tsx   │
                    │  (Server)   │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
    │TestRun  │      │Results  │      │Behaviors│
    │ Detail  │      │ + Prompts│      │+Metrics │
    └────┬────┘      └────┬────┘      └────┬────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────────┐
                    │ TestRunMainView │
                    │   (Client)      │
                    └──────┬──────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────────┐
    │FilterBar│      │TestsList│      │DetailPanel  │
    └─────────┘      └─────────┘      └─────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         │                    │                    │
                   ┌─────▼──────┐      ┌─────▼──────┐      ┌─────▼──────┐
                   │ OverviewTab│      │ MetricsTab │      │ HistoryTab │
                   └────────────┘      └────────────┘      └────────────┘
```

## Comparison: Old vs New

### Old Design

```
- DataGrid with pagination
- Flat table view
- Limited filtering
- Behavior columns (hard to read)
- Modal for details
- Desktop-focused
- Click row → Navigate to test page
```

### New Design

```
- List + Detail split view
- Rich visual indicators
- Advanced filtering & search
- Tabbed detail interface
- In-page detail view
- Mobile-first responsive
- Click test → Show in panel (stay on page)
- Behavior accordions (easier to read)
```

## Key Improvements

1. **Discoverability**: Filters and search are prominent
2. **Information Density**: More data visible without scrolling
3. **Visual Hierarchy**: Color-coded statuses, clear sections
4. **Mobile Experience**: Fully responsive, touch-friendly
5. **Navigation**: No page changes, instant feedback
6. **Flexibility**: Client-side filtering, no server round-trips
7. **Performance**: All data loaded once, fast filtering
8. **Accessibility**: Better keyboard navigation, ARIA labels
9. **Modern UI**: Card-based, animated, polished
10. **Extensibility**: Easy to add new tabs, filters, features
