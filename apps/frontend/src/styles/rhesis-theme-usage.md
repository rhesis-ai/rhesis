# Rhesis AI Theme Usage Guide

## UI Revamp — New in Phase 1 (2026-05-19)

### Greyscale Palette (Figma-aligned)

All greyscale tokens live at `theme.palette.greyscale` and are correctly switched for light/dark.

```tsx
const theme = useTheme();

theme.palette.greyscale.title; // #1a1c20 (headings)
theme.palette.greyscale.body; // #2a2e36 (body copy, cell text)
theme.palette.greyscale.subtitle; // #7f8a9b (category labels, subdued)
theme.palette.greyscale.border; // #cdd2da (table dividers, input borders)
theme.palette.greyscale.surface1; // #f7f8f9 (table header bg, hover rows)
theme.palette.greyscale.surface2; // #eef0f3 (chip default bg, card bg)
```

### New Typography Variants (Figma scale)

```tsx
<Typography variant="bodyLReg">Body L Regular — 16px/24px/400</Typography>
<Typography variant="bodyMReg">Body M Regular — 14px/22px/400</Typography>
<Typography variant="bodyMBold">Body M Bold — 14px/22px/700</Typography>
<Typography variant="bodySReg">Body S Regular — 12px/18px/400</Typography>
<Typography variant="captionBold">Caption Bold — 12px/18px/600</Typography>
```

Updated `h4`: 28px / 33.6px / weight 700 (matches Figma H4/Bold).

### Elevation Tokens

```tsx
import { ELEVATION } from '@/styles/theme';

// Box shadow values for sx props
ELEVATION.xs; // 0px 2px 4px rgba(84, 90, 101, 0.25)  ← default Paper elevation 1
ELEVATION.s; // 0px 16px 32px -4px ...
ELEVATION.m; // ...
ELEVATION.l; // ...
ELEVATION.xl; // ...

// Also available on theme object:
theme.elevation.xs; // same string value
```

### Pill Button Variant

```tsx
<Button variant="pill">Label</Button>
// Fully rounded (borderRadius: 999), outlined style, activatable via className/aria
```

---

## Color Palette Usage

### Primary Colors

```tsx
import { useTheme } from '@mui/material/styles';

const theme = useTheme();

// Primary Blue: #50B9E0
theme.palette.primary.main;

// Primary Light Blue: #97D5EE
theme.palette.primary.light;

// Primary CTA Blue: #2AA1CE
theme.palette.primary.dark;
```

### Background Colors

```tsx
// Light backgrounds (light mode)
theme.palette.background.default; // #F2F9FD - Light Background 1
theme.palette.background.paper; // #FFFFFF - White Background
theme.palette.background.light1; // #F2F9FD
theme.palette.background.light2; // #E4F2FA
theme.palette.background.light3; // #C2E5F5
theme.palette.background.light4; // #97D5EE
```

### Text Colors

```tsx
theme.palette.text.primary; // #3D3D3D - Dark Text
theme.palette.text.secondary; // #1A1A1A - Dark Black
```

### CTA Colors

```tsx
theme.palette.secondary.main; // #FD6E12 - Secondary CTA Orange
theme.palette.secondary.light; // #FDD803 - Accent Yellow
theme.palette.secondary.dark; // #1A1A1A - Dark Black
```

## Typography Usage

### Font Families

- **Sora**: Used for major headings (h1, h2, h3)
- **Be Vietnam Pro**: Used for body text, UI elements, and secondary headings (h4, h5, h6)

### Typography Variants

```tsx
<Typography variant="h1">Major Title (Sora Semibold)</Typography>
<Typography variant="h2">Section Heading (Sora Medium)</Typography>
<Typography variant="h3">Subsection (Sora Regular)</Typography>
<Typography variant="h4">UI Heading (Be Vietnam Pro Semibold)</Typography>
<Typography variant="body1">Body Text (Be Vietnam Pro Regular)</Typography>
<Typography variant="body2">Secondary Text (Be Vietnam Pro Light)</Typography>
<Typography variant="caption">Caption Text (Be Vietnam Pro Light)</Typography>
```

## Button Usage

### Primary Buttons (Main Actions)

```tsx
<Button variant="contained" color="primary">
  Primary Action (CTA Blue #2AA1CE background, white text)
</Button>
```

### Secondary Buttons (Alternative Actions)

```tsx
<Button variant="contained" color="secondary">
  Secondary Action (Orange #FD6E12 background, white text)
</Button>
```

### Outlined Buttons (Tertiary Actions)

```tsx
<Button variant="outlined" color="primary">
  Tertiary Action (CTA Blue #2AA1CE border/text, transparent background)
</Button>

<Button variant="outlined" color="secondary">
  Alternative Tertiary Action (Orange #FD6E12 border/text, transparent background)
</Button>
```

### Text Buttons (Subtle Actions)

```tsx
<Button variant="text" color="primary">
  Subtle Action (Blue text, no background/border)
</Button>
```

### Button Hierarchy Guidelines

- **Contained Primary**: Most important actions (Submit, Save, Execute)
- **Contained Secondary**: Important alternative actions (Alternative CTAs)
- **Outlined Primary**: Secondary actions (Cancel, Download, Edit)
- **Outlined Secondary**: Less common secondary actions
- **Text**: Subtle actions (Links, minor actions)

### Example Usage Patterns

```tsx
// Form actions
<Button variant="contained" color="primary">Save Changes</Button>
<Button variant="outlined" color="primary">Cancel</Button>

// Data actions
<Button variant="contained" color="primary">Execute Test</Button>
<Button variant="outlined" color="primary">Download Results</Button>
<Button variant="text" color="primary">View Details</Button>
<Button variant="text" color="primary">
  Text Action (Primary Blue #50B9E0)
</Button>
```

## Chart Colors

### Line Charts

```tsx
const theme = useTheme();
const lineColors = theme.chartPalettes.line;
// ['#50B9E0', '#FD6E12', '#2AA1CE', '#FDD803']
```

### Pie Charts

```tsx
const pieColors = theme.chartPalettes.pie;
// ['#97D5EE', '#50B9E0', '#2AA1CE']
```

### Status Colors

```tsx
const statusColors = theme.chartPalettes.status;
// ['#2AA1CE', '#FDD803', '#FD6E12'] - success, warning, error
```

## Custom Components

### Cards with Rhesis AI Styling

```tsx
<Card
  sx={{
    backgroundColor: theme.palette.background.paper,
    boxShadow: '0 2px 8px rgba(80, 185, 224, 0.08)',
  }}
>
  <CardContent>
    <Typography variant="h5" color="text.primary">
      Card Title
    </Typography>
  </CardContent>
</Card>
```

### Background Sections

```tsx
<Box
  sx={{
    backgroundColor: theme.palette.background.light2,
    padding: 3,
    borderRadius: 2,
  }}
>
  Content with light blue background
</Box>
```
