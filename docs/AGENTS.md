# Documentation Rules

Apply whenever creating, modifying, or generating any documentation in this directory. Framework:
Nextra, which processes MDX (Markdown + JSX).

## Writing rules

Docs describe the current product for a reader who wants to do something — not to sell, reassure,
or restate what the page structure already shows.

### Tone

- **No empty sales style.** Delete hype and reassurance that carries no information ("That's it!",
  "improving the user experience"). State what a command does, not how easy it is. Concrete, true
  promises are fine where they set expectations ("running in under 5 minutes") — once, in a
  getting-started/quick-start intro, not repeated in every heading.
- **Ban "simply", "easily", "just", "powerful", "seamless", "comprehensive".** If a step needs
  "simply" to sound simple, rewrite the step. Replace the adjective with a verifiable claim where
  one exists: "drop-in replacement for the OpenAI SDK" over "powerful integration"; "minimal
  changes to your code" over "seamless".
- **Facts first.** The first sentence of a page defines its subject ("Prompt management is a
  systematic approach to storing, versioning, and retrieving prompts") — no welcome paragraph, no
  framing before it. A brief thank-you atop a contributing guide is fine; skip pleasantries and
  exclamation marks elsewhere.
- **No decorative emojis** in prose or headings (✅ 🚀 📦 ℹ️) — use "Note:" / "Warning:" / "Tip:"
  or a `Callout`. Emojis passed as component props (e.g. `NextStepCard` icons) are a deliberate
  design element and stay.
- **Marketing exception.** Product Tour, Welcome, and to a degree Core Concepts may keep
  promotional copy; there, target redundancy and wrong facts, not tone.

### Redundancy

- **Say each fact once per page.** Keep one canonical spot; delete echoes across overview bullets,
  code comments, and later sections. Exception: short audience-routing callouts (**"Prefer code?"
  → Python SDK**) are fine even when the topic is covered elsewhere on the page.
- **Say each fact once across the site.** If another page owns the topic, link instead of
  restating; prefer the docs site as canonical. Core entity definitions (project, endpoint, test
  set, test run, …) live in `concepts.mdx` and nowhere else — feature pages link there.
  Landing/index pages may repeat a navigation block.
- **Delete "Overview" / "What You Get" sections that restate the page title or the headings below
  them.** An Overview *page* of a section is different: a short hub (~250 words) — the problem the
  feature solves, how it addresses it, one screenshot, links to subpages.

### Obviousness and scope

- **Don't narrate a command's internals.** Document what the reader must do beforehand, type, and
  will see — not the steps hidden inside the script. If hidden behavior genuinely matters (async
  processing, request flow), one mermaid diagram with a one-line annotation beats paragraphs.
- **Don't explain standard tools** (what ruff/pytest/Docker/git are). Show the command.
- **Don't list obvious prerequisites** ("Git installed"). Compress to one line only when a version
  constraint matters (Python 3.10+). Non-obvious prerequisites are a one-line link, not a section.
- **No file trees or tables describing self-describing files** (`docker-compose.yml` — "Docker
  Compose configuration"). Keep such listings only when the description is non-obvious.
- **Keep code-block comments to non-obvious facts.** `# 1. Clone the repository` above
  `git clone` is noise; `# pulls prebuilt images from GHCR` earns its place.
- **One page, one job.** If a section grows into its own topic, split it out and link, keeping only
  the core subset inline.
- **Trim option menus to the recommended path.** Present the default once; mention alternatives in
  a single line with a link. When options must coexist, route by situation ("just debugging →
  tracing; iterating on prompts → prompt management").
- **Drop version annotations** ("(v0.6.9+)") from headings and prose — version history belongs in
  the changelog.
- **Getting-started pages document the user-facing surface only.** Cut service internals
  (deployment modes, storage-layout tables, backend config payloads, generic best-practices and
  troubleshooting boilerplate).
- **"Next steps" are concrete actions, not page pointers** ("Group traces into sessions"), not card
  grids restating navigation ("Explore the Product Tour →").

### Terminology

- **Call it an "LLM application" (or "AI agent"), never "AI application" / "generative AI
  application".** Default to **LLM application**; use **AI agent** only where the context is
  specifically about agents (reasoning, tool calls, multi-turn goal pursuit). Leave proper names
  untouched (Garak's "Generative AI Red-teaming and Assessment Kit", the "Pydantic AI" framework,
  example strings like `name="My AI App"`). Glossary term text lives in
  `content/glossary/glossary-terms.jsonl` — edit the source and regenerate with
  `node scripts/generate-glossary-pages.js`, not the generated `index.mdx` files.

### Verify while writing

Check every concrete claim a page makes — commands, env vars, API routes and fields, defaults,
rate limits, UI labels, code samples — against the code. A wrong claim must be fixed or cut, never
carried over.

## MDX mechanics

### Escaping curly braces

MDX interprets anything inside `{...}` as a JSX expression. Escape curly braces whenever you want
literal text:

```mdx
GOOD: API PUT /test_results/\{id\}
BAD:  API PUT /test_results/{id} ← causes "ReferenceError: id is not defined"
```

Common scenarios: API endpoint paths (`/api/users/\{userId\}/profile`), template strings
(`"Hello \{name\}"`), headings (`### Using \{variable\} in templates`), JSON examples
(`\{"key": "value"\}`), path parameters, variable placeholders (`\{count\} items`).

**When NOT to escape**: inside fenced code blocks (` ` ``` or `~~~`) or inline code
(`` `{id}` ``) — both are already literal.

### Material-UI icons in MDX

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

### Colour, type, and design tokens

Design tokens live in `src/styles/tokens.css` as `--rh-*` custom properties, synced by hand from the
marketing site's `@theme` block (`website/src/styles/tailwind.css`). Rules:

- **Never hardcode a hex in a component or in `globals.css`.** Use a token. If no token fits, add
  one to `tokens.css` rather than inlining a value. The `--rhesis-*` names are legacy aliases kept
  pointing at `--rh-*`; prefer `--rh-*` in new code.
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

### Files and structure

- Kebab-case file names (`test-result-status.mdx`); organize by feature/topic, not file type.
- Include code examples with a language tag (` ```python `, ` ```typescript `, ` ```bash `).

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

### Before committing

Build locally and check that links resolve — watch especially for unescaped curly braces.
