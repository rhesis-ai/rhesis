# Documentation Rules

**These rules MUST be applied whenever creating, modifying, or generating any documentation in
this directory.** Framework: Nextra, which processes MDX (Markdown + JSX).

## Quick checklist

- Escape ALL curly braces in text: `\{id\}`, `\{value\}`, `\{placeholder\}`
- Remove decorative emojis (use "Note:", "Warning:", "Tip:" instead)
- Follow existing documentation style and structure
- Include code examples with language tags (` ```python `, ` ```typescript `, ` ```bash `)
- Test that the documentation builds without errors
- Link to related documentation pages

## Escaping curly braces

MDX interprets anything inside `{...}` as a JSX expression. Escape curly braces whenever you want
literal text:

```mdx
✅ GOOD: API PUT /test_results/\{id\}
❌ BAD: API PUT /test_results/{id} ← causes "ReferenceError: id is not defined"
```

Common scenarios: API endpoint paths (`/api/users/\{userId\}/profile`), template strings
(`"Hello \{name\}"`), headings (`### Using \{variable\} in templates`), JSON examples
(`\{"key": "value"\}`), path parameters, variable placeholders (`\{count\} items`).

**When NOT to escape**: inside fenced code blocks (` ` ``` or `~~~`) or inline code
(`` `{id}` ``) — both are already literal.

## Material-UI icons in MDX

MDX files cannot directly import Material-UI icons — module resolution fails. **Never** import
`@mui/icons-material/*` directly in `.mdx`. Instead:

1. Create a JSX component in `src/components/` that imports the icon:

   ```jsx
   "use client";
   import React from "react";
   import IconName from "@mui/icons-material/IconName";
   import { InfoCardHorizontal } from "./InfoCardHorizontal";

   export const MyComponent = () => (
     <InfoCardHorizontal icon={IconName} title="..." description="..." />
   );
   ```

2. Register it in `src/mdx-components.js`:

   ```js
   import { MyComponent } from "./components/MyComponent";

   export function useMDXComponents(components) {
     return { ...themeComponents, ...components, MyComponent };
   }
   ```

3. Use it in MDX with no imports: `<MyComponent />`

Examples already following this pattern: `FeatureOverview.jsx`, `ArchitectureOverview.jsx`,
`PlatformFeatures.jsx`.

## Colour, type, and design tokens

Design tokens live in `src/styles/tokens.css` as `--rh-*` custom properties, synced by hand from the
marketing site's `@theme` block (`website/src/styles/tailwind.css`). Rules:

- **No hex for anything on the theme or brand scale** — surfaces, text, borders, accents, CTAs — in
  components or in `globals.css`. Use a token; if none fits, add one to `tokens.css` rather than
  inlining a value. That includes CSS-variable *fallbacks*: write
  `var(--card-bg, var(--rh-surface))`, not `var(--card-bg, #ffffff)`, or the fallback silently
  renders a light surface in dark mode.
- **Literal hex is correct for fixed decorative artwork**, and tokenising it would be wrong: the
  German flag in `FooterOriginBadge`, the macOS window dots in `CodeBlock`/`FileTree`, and the
  terminal palette and tint ramps in `FileTree`/`ChatExchange`/`ToolPurposeChip`. These carry meaning
  independent of the theme. If a value would look broken in the other theme, it wants a token; if it
  would look broken in any *other colour*, it wants to stay literal.
- The `--rhesis-*` names are legacy aliases kept pointing at `--rh-*`; prefer `--rh-*` in new code.
- **Colour is neutral by default.** Chrome (navbar, sidebar, footer, body copy, headings, primary
  buttons) sits on the neutral scale; the brand blues are for accents and links. Orange is for CTAs
  only — don't reintroduce it as an icon or card accent.
- **Check whether a surface is theme-following before tokenising it.** `CodeBlock` and `FileTree`
  render a dark terminal surface in *both* themes, with Shiki colours chosen for a dark background.
  They use the theme-invariant `--rh-codeblock-*` tokens; pointing them at `--rh-surface`/`--rh-text`
  turns them white in light mode and makes the syntax colours unreadable.
- **Fonts**: Sora for display/headings, Geist for UI and body, Geist Mono for code and the uppercase
  eyebrow labels. All self-hosted woff2 in `public/fonts/`.
- **Nextra's own accent ramp is not set in CSS.** It comes from the `color` prop on `<Head>` in
  `src/app/layout.jsx`, which Nextra emits as an inline `<style>` that beats any stylesheet. Nextra
  derives `primary-50` … `primary-800` from those HSL values, and the active sidebar link is
  `bg-primary-100` + `text-primary-800`. Change the prop; do not override the generated `x:` classes.

## Directory structure

```
docs/
├── src/
│   ├── components/               # Reusable JSX components for MDX
│   ├── app/                      # Next.js app directory
│   └── mdx-components.js         # MDX component registry
├── content/                      # All documentation content (MDX files)
│   ├── _meta.tsx                 # Root navigation config
│   ├── getting-started/, platform/, sdk/
│   └── development/{backend,frontend,worker}/
└── README.md
```

Each directory needs a `_meta.tsx` for navigation:

```typescript
import type { MetaRecord } from "nextra";

const meta: MetaRecord = {
  index: "Overview",
  "getting-started": "Getting Started",
};

export default meta;
```

## Style

- Match the tone/structure/heading hierarchy of existing docs.
- Kebab-case file names (`test-result-status.mdx`); organize by feature/topic, not file type.
- Build locally and check links before committing — watch especially for unescaped curly braces.
