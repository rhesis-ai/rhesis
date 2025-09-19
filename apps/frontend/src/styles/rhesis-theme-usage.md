# Rhesis AI Theme Usage Guide

## Color Palette Usage

### Primary Colors
```tsx
import { useTheme } from '@mui/material/styles';

const theme = useTheme();

// Primary Blue: #50B9E0
theme.palette.primary.main

// Primary Light Blue: #97D5EE  
theme.palette.primary.light

// Primary CTA Blue: #2AA1CE
theme.palette.primary.dark
```

### Background Colors
```tsx
// Light backgrounds (light mode)
theme.palette.background.default    // #F2F9FD - Light Background 1
theme.palette.background.paper      // #FFFFFF - White Background
theme.palette.background.light1     // #F2F9FD
theme.palette.background.light2     // #E4F2FA
theme.palette.background.light3     // #C2E5F5
theme.palette.background.light4     // #97D5EE
```

### Text Colors
```tsx
theme.palette.text.primary          // #3D3D3D - Dark Text
theme.palette.text.secondary        // #1A1A1A - Dark Black
```

### CTA Colors
```tsx
theme.palette.secondary.main        // #FD6E12 - Secondary CTA Orange
theme.palette.secondary.light       // #FDD803 - Accent Yellow
theme.palette.secondary.dark        // #1A1A1A - Dark Black
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

### Primary Buttons
```tsx
<Button variant="contained" color="primary">
  Primary Action (CTA Blue #2AA1CE)
</Button>
```

### Secondary Buttons
```tsx
<Button variant="contained" color="secondary">
  Secondary Action (Orange #FD6E12)
</Button>
```

### Text Buttons
```tsx
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
<Card sx={{ 
  backgroundColor: theme.palette.background.paper,
  boxShadow: '0 2px 8px rgba(80, 185, 224, 0.08)'
}}>
  <CardContent>
    <Typography variant="h5" color="text.primary">
      Card Title
    </Typography>
  </CardContent>
</Card>
```

### Background Sections
```tsx
<Box sx={{ 
  backgroundColor: theme.palette.background.light2,
  padding: 3,
  borderRadius: 2
}}>
  Content with light blue background
</Box>
```
