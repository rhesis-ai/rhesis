---
name: docs-social-images
description: How the docs site generates per-page og:image cards, and the cache and font traps when changing them. Use when editing the OG card design, og-theme.js, or a page's social preview image.
---

# Docs social preview images

Every page's `og:image` is generated per page by `docs/src/app/api/og/route.jsx` — title,
description and section come from the page's own MDX, resolved through `lib/og-page.js`.

**Adding a page needs nothing.** The card is generated from its frontmatter automatically.

## Three traps

- **Changing the card design means bumping `OG_VERSION`** in `lib/og-theme.js`. Crawlers cache
  social images by URL; without a new `v=`, LinkedIn and Slack keep serving the old picture.
  Editing a page's own title or description needs nothing — `h=` in the URL is a hash of the card
  text, so it changes on its own.
- **Card colours are literal hex in `lib/og-theme.js`, copied from `tokens.css`.** satori never
  sees a stylesheet, so `var(--rh-*)` resolves to nothing. This is the one place hex is expected —
  change both files together. See the `docs-design-tokens` skill for the token rules everywhere
  else.
- **Fonts are TTF subsets in `docs/public/fonts/og/`**, not the woff2 the site uses: satori cannot
  decode woff2. Regenerate with `docs/scripts/generate-og-fonts.py` after a font change.

## Hand-made images

A page that needs one sets `ogImage: /path.png` in frontmatter. Use PNG or JPEG — social crawlers
do not render webp reliably.
