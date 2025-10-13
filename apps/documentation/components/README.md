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

### Footer

A comprehensive, reusable footer component that matches the main Rhesis website structure with proper theming and responsive design.

**Usage in MDX files:**

```mdx
import Footer from '@/components/Footer'

<Footer />
```

**Usage with customization:**

```jsx
import Footer from '@/components/Footer'

// Basic usage
<Footer />

// With additional links
<Footer
  additionalLinks={[
    { name: "Custom Link", href: "/custom", section: "product" },
    { name: "Legal Link", href: "/legal", section: "legal", external: true }
  ]}
/>

// With custom sections
<Footer
  customSections={[
    {
      title: "Resources",
      links: [
        { name: "Blog", href: "/blog" },
        { name: "Tutorials", href: "/tutorials" }
      ]
    }
  ]}
/>

// Hide copyright
<Footer showCopyright={false} />
```

**Features:**

- **Product Links**: Platform, SDK, Repository
- **Documentation Links**: Getting started, Test Generation, Metrics
- **Company Links**: About us, Careers, Contact us
- **Legal Links**: Imprint, Privacy, Terms
- **Responsive Design**: Adapts to mobile, tablet, and desktop screens
- **Theme Support**: Automatic light/dark mode with proper contrast
- **Extensible**: Add custom sections and links via props
- **Accessibility**: Focus states, proper ARIA labels, keyboard navigation

**Props:**

- `showCopyright` (boolean): Show/hide copyright notice (default: true)
- `additionalLinks` (array): Add extra links to existing sections
- `customSections` (array): Add entirely new footer sections
- `className` (string): Additional CSS classes

**Design:**

- Grid layout that adapts to screen size (3+ columns on desktop, 2 on tablet, 1 on mobile)
- Consistent with Rhesis brand colors and typography
- Proper spacing and visual hierarchy
- Hover effects and smooth transitions

## Creating New Components

1. Create your component file in this directory
2. Export your component as named or default export
3. Add path alias support in `tsconfig.json` if needed
4. Document your component in this README

## Styling Guidelines

### Rhesis Brand Colors

Use the CSS custom properties defined in `styles/globals.css`:

**Primary Blues:**

- `--rhesis-primary-main: #50B9E0` (RGB: 80, 185, 224)
- `--rhesis-primary-light: #97D5EE` (RGB: 151, 213, 238)
- `--rhesis-primary-dark: #2AA1CE` (CTA Blue)
- `--rhesis-primary-darker: #3BC4F2` (Hover Blue)

**Backgrounds:**

- `--rhesis-bg-lightest: #f2f9fd`
- `--rhesis-bg-light: #e4f2fa`
- `--rhesis-bg-medium: #C2E5F5`
- `--rhesis-bg-blue: #97D5EE`
- `--rhesis-bg-white: #FFFFFF`

**Text Colors:**

- `--rhesis-text-primary: #3d3d3d` (Main text)
- `--rhesis-text-dark: #1A1A1A` (RGB: 26, 26, 26)

**CTA Colors:**

- `--rhesis-cta-blue: #2AA1CE`
- `--rhesis-cta-orange: #FD6E12` (RGB: 253, 110, 18)

**Accent Colors:**

- `--rhesis-accent-yellow: #FDD803` (RGB: 253, 216, 3)

### Typography

- **Headings**: Sora font family
- **Body text**: Be Vietnam Pro font family

### Best Practices

- Support both light and dark modes
- Use CSS variables for theme-aware styling
- Follow responsive design patterns (mobile-first)
- Use `var(--rhesis-*)` for consistent brand colors
