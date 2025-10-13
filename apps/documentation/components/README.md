# Documentation Components

This directory contains reusable React components for the Rhesis documentation site.

## Available Components

### FeatureOverview

A visually appealing overview card component that showcases Rhesis platform features.

**Usage in MDX files:**

```mdx
import { FeatureOverview } from '@/components/FeatureOverview'

<FeatureOverview />
```

**Features displayed:**
- **Test Generation**: AI-powered test scenario creation, domain expert knowledge integration, automated edge case coverage
- **Endpoints**: REST and WebSocket support, multi-provider LLM integration, real-time testing execution
- **Evaluation**: LLM-based quality metrics, custom evaluation criteria, detailed performance analytics
- **Collaborative Platform**: Team-based project management, SDK and API-first architecture, comprehensive test result tracking

**Design:**
- Responsive grid layout (3 columns on desktop, 1 column on mobile)
- Full-width platform feature card at the bottom
- Dark mode support using Nextra theme
- Rhesis brand colors (#2AA1CE primary blue)
- Custom fonts (Sora for titles, Be Vietnam Pro for body text)

**Dependencies:**
- None (uses inline SVG icons instead of external icon libraries)
- Works with Nextra's dark mode out of the box

### Button

A custom button component with Rhesis brand styling.

**Usage:**

```jsx
import Button, { PrimaryButton, SecondaryButton } from '@/components/Button'

<Button variant="primary">Click me</Button>
<PrimaryButton>Primary Action</PrimaryButton>
```

### ThemeAwareLogo

A logo component that automatically switches between light and dark variants based on the current theme.

## Creating New Components

1. Create your component file in this directory
2. Export your component as named or default export
3. Add path alias support in `tsconfig.json` if needed
4. Document your component in this README

## Styling Guidelines

- Use Rhesis brand colors:
  - Primary Blue: `#2AA1CE`
  - Primary Light: `#50B9E0`
  - Primary Dark: `#3BC4F2`
  - Secondary Orange: `#FD6E12`
  - Accent Yellow: `#FDD803`
- Use brand fonts:
  - Headings: Sora
  - Body text: Be Vietnam Pro
- Support both light and dark modes
- Use CSS variables for theme-aware styling
- Follow responsive design patterns (mobile-first)
