# Hardcoded Styles Check GitHub Action

This GitHub Action automatically checks Pull Requests for hardcoded styles that should use theme values instead, ensuring consistent design system usage across the frontend codebase.

## What it checks

The action scans TypeScript/JavaScript files in `apps/frontend/src/` for:

### 🎨 **Colors**
- Hardcoded hex colors (e.g., `#50B9E0`, `#FD6E12`)
- RGB/RGBA color values (e.g., `rgb(80, 185, 224)`)
- **Should use**: `theme.palette.*` values

### 📝 **Font Sizes**
- Hardcoded font sizes in px, rem, em (e.g., `fontSize: '14px'`)
- **Should use**: Typography variants (`variant="body2"`) or `theme.typography.*`

### 📏 **Spacing**
- Hardcoded margin/padding values (e.g., `margin: '16px'`, `padding: '24px'`)
- **Should use**: `theme.spacing()` or MUI system props (`m={2}`, `p={3}`)

### 🌟 **Elevations**
- Hardcoded box-shadow values
- **Should use**: `theme.elevation.*` or component `elevation` prop

### 🔘 **Border Radius**
- Hardcoded border radius values that don't match theme standards

## What it ignores

The checker intelligently ignores:

- **SVG content**: Colors in SVG paths, fills, and strokes
- **Theme files**: The theme definition file itself (`theme.ts`)
- **CSS Modules**: `.module.css` files
- **Test files**: `.test.*` and `.spec.*` files
- **Small adjustments**: 1-4px spacing values for micro-adjustments
- **System colors**: Pure black/white (`#000`, `#fff`)
- **Transparent overlays**: Common rgba patterns for overlays
- **Theme property access**: Lines already using `theme.palette.*`
- **MUI system props**: Lines using `color="primary"`, `m={2}`, etc.

## How it works

### Trigger
The action runs automatically on:
- Pull requests to `main` or `develop` branches  
- When files in `apps/frontend/src/**/*.{ts,tsx,js,jsx}` are changed

### Process
1. **Checkout code** with git history for diff comparison
2. **Setup Node.js** environment
3. **Run style checker** on changed files only (for efficiency)
4. **Report violations** with detailed suggestions
5. **Comment on PR** if violations are found (action will fail)

### Output
If violations are found, the action will:
- ❌ **Fail the check** (preventing merge until fixed)
- 💬 **Comment on the PR** with detailed violation report
- 📋 **List specific files, lines, and suggestions** for each violation

## Example violations and fixes

### Colors
```tsx
// ❌ Bad - hardcoded color
sx={{ color: '#50B9E0' }}

// ✅ Good - theme color
sx={{ color: 'primary.main' }}
// or
sx={{ color: theme.palette.primary.main }}
```

### Font Sizes
```tsx
// ❌ Bad - hardcoded font size
sx={{ fontSize: '14px' }}

// ✅ Good - typography variant
<Typography variant="body2">Text</Typography>
// or
sx={{ fontSize: theme.typography.body2.fontSize }}
```

### Spacing
```tsx
// ❌ Bad - hardcoded spacing
sx={{ margin: '16px', padding: '24px' }}

// ✅ Good - theme spacing
sx={{ m: 2, p: 3 }} // Uses theme.spacing()
// or
sx={{ 
  margin: theme.spacing(2), 
  padding: theme.spacing(3) 
}}
```

### Elevations
```tsx
// ❌ Bad - hardcoded shadow
sx={{ boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}

// ✅ Good - theme elevation
<Paper elevation={2}>Content</Paper>
// or for custom usage
sx={{ boxShadow: theme.shadows[2] }}
```

## Manual usage

You can run the checker locally:

```bash
# Check all files
node scripts/check-hardcoded-styles.js

# The script automatically detects if you're in a git repo
# and will check only changed files in PR context
```

## Configuration

The checker is configured in `scripts/check-hardcoded-styles.js` with:

- **Theme values**: Extracted from `apps/frontend/src/styles/theme.ts`
- **Exclude patterns**: Files/directories to skip
- **Ignore patterns**: Code patterns that are acceptable
- **Violation types**: What types of hardcoded values to detect

## Files

- **Script**: `scripts/check-hardcoded-styles.js` - The main checking logic
- **Workflow**: `.github/workflows/check-hardcoded-styles.yml` - GitHub Action definition  
- **Theme reference**: `apps/frontend/src/styles/theme.ts` - Source of truth for theme values
- **Usage guide**: `apps/frontend/src/styles/rhesis-theme-usage.md` - Detailed theme usage examples

## Benefits

✅ **Consistent Design**: Ensures all components use the same color palette, spacing, and typography  
✅ **Theme Compliance**: Prevents drift from the design system  
✅ **Easy Maintenance**: Centralized theme values make global changes simple  
✅ **Dark Mode Ready**: Theme-based styles automatically work with light/dark mode switching  
✅ **Developer Education**: Teaches proper theme usage through actionable feedback  

## Troubleshooting

### False Positives
If the checker flags valid hardcoded values:
1. Check if the pattern should be added to `IGNORE_PATTERNS` in the script
2. Consider if the value should actually use a theme value
3. For SVG content, ensure it's properly detected as SVG markup

### Missing Theme Values  
If you need a hardcoded value that should be in the theme:
1. Add it to `apps/frontend/src/styles/theme.ts`
2. Update the `THEME_VALUES` object in the checker script
3. Update documentation in `rhesis-theme-usage.md`

### Performance
The checker only scans changed files in PR context for efficiency. For full codebase scans, run locally with all files.
