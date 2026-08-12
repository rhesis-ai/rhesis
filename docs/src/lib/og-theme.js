/**
 * Card design for the generated social preview images (`/api/og`).
 *
 * Two things here are deliberate exceptions to the usual rules:
 *
 * 1. Literal hex, not `--rh-*` tokens. satori (inside `next/og`) renders from
 *    inline styles alone — it never sees a stylesheet, so CSS custom properties
 *    resolve to nothing. The values below are copied by hand from
 *    `styles/tokens.css`; change them together.
 * 2. Light palette only. A social card has no theme to follow, and the
 *    marketing site's OG images are all on the light canvas.
 */

export const OG_SIZE = { width: 1200, height: 630 }

/** Bumped when the card design changes, to bust crawler caches — see getOpenGraphImage(). */
export const OG_VERSION = '1'

export const OG_COLORS = {
  canvas: '#ffffff',
  heading: '#111827',
  text: '#2c2c2c',
  textSecondary: '#4b5563',
  textMuted: '#9ca3af',
  border: '#e5e7eb',
  blue: '#50b9e0',
  blueCta: '#2aa1ce',
  yellow: '#fdd803',
}

/**
 * Font sizes step down as the title grows, so a long page title still fits
 * three lines at 1200x630 instead of overflowing the card.
 *
 * @param {string} title
 * @returns {number} font size in px
 */
export function titleFontSize(title) {
  const length = (title || '').length
  if (length <= 24) return 76
  if (length <= 44) return 64
  if (length <= 70) return 54
  return 46
}

/**
 * Truncates on a word boundary and appends an ellipsis.
 *
 * satori has no reliable line clamp, so text is cut by length here instead —
 * the limits are picked to match the font sizes above.
 *
 * @param {string} text
 * @param {number} limit
 * @returns {string}
 */
export function truncate(text, limit) {
  const value = (text || '').replace(/\s+/g, ' ').trim()
  if (value.length <= limit) return value

  const cut = value.slice(0, limit)
  const lastSpace = cut.lastIndexOf(' ')
  return `${(lastSpace > limit * 0.6 ? cut.slice(0, lastSpace) : cut).replace(/[,;:.\s]+$/, '')}…`
}

/**
 * Drops a trailing brand suffix from a page title. Several pages carry
 * "– Rhesis" in frontmatter for the browser tab; on a card that already shows
 * the logo, and in an image alt that appends the site name, it is just noise.
 *
 * @param {string} title
 * @returns {string}
 */
export function stripBrandSuffix(title) {
  if (!title) return title
  return title.replace(/\s*[–—|]\s*Rhesis(\s+[\w.]+){0,2}\s*$/i, '').trim() || title
}

export const TITLE_LIMIT = 90
export const DESCRIPTION_LIMIT = 130
