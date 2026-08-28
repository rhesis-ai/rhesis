---
name: docs-design-tokens
description: Colour, font and design-token rules for the docs site — when hex is banned, when it is correct, and which surfaces ignore the theme. Use when styling docs components or editing CSS under docs/src.
---

# Docs design tokens

Design tokens live in `docs/src/styles/tokens.css` as `--rh-*` custom properties, synced by hand
from the marketing site's `@theme` block (`website/src/styles/tailwind.css`, a separate repo).

## Colour

- **No hex for anything on the theme or brand scale** — surfaces, text, borders, accents, CTAs — in
  components or in `globals.css`. Use a token; if none fits, add one to `tokens.css` rather than
  inlining a value. That includes CSS-variable *fallbacks*: write
  `var(--card-bg, var(--rh-surface))`, not `var(--card-bg, #ffffff)`, or the fallback silently
  renders a light surface in dark mode.
- **Literal hex is correct for fixed decorative artwork**, and tokenising it would be wrong: the
  German flag in `FooterOriginBadge`, the macOS window dots in `CodeBlock`/`FileTree`, and the
  terminal palette and tint ramps in `FileTree`/`ChatExchange`/`ToolPurposeChip`. These carry
  meaning independent of the theme. If a value would look broken in the other theme, it wants a
  token; if it would look broken in any *other colour*, it wants to stay literal.
- **Colour is neutral by default.** Chrome (navbar, sidebar, footer, body copy, headings, primary
  buttons) sits on the neutral scale; the brand blues are for accents and links. Orange is for CTAs
  only — don't reintroduce it as an icon or card accent.
- The `--rhesis-*` names are legacy aliases kept pointing at `--rh-*`; prefer `--rh-*` in new code.

## Theme-invariant surfaces

**Check whether a surface follows the theme before tokenising it.** `CodeBlock` and `FileTree`
render a dark terminal surface in *both* themes, with Shiki colours chosen for a dark background.
They use the theme-invariant `--rh-codeblock-*` tokens; pointing them at `--rh-surface`/`--rh-text`
turns them white in light mode and makes the syntax colours unreadable.

## Fonts

Sora for display/headings, Geist for UI and body, Geist Mono for code and the uppercase eyebrow
labels. All self-hosted woff2 in `docs/public/fonts/`.

## Nextra's accent ramp

**Not set in CSS.** It comes from the `color` prop on `<Head>` in `docs/src/app/layout.jsx`, which
Nextra emits as an inline `<style>` that beats any stylesheet. Nextra derives `primary-50` …
`primary-800` from those HSL values, and the active sidebar link is `bg-primary-100` +
`text-primary-800`. Change the prop; do not override the generated `x:` classes.
