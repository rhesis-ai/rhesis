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
