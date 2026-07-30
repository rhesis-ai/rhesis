/**
 * GradientBackdrop
 *
 * Soft gradient wash (light) / aurora glow (dark) behind the page, ported from
 * the marketing site's SoftGradientWash and DarkAuroraGlow. All the painting
 * lives in `.rhesis-backdrop` in globals.css.
 *
 * Rendered ONCE globally, from `src/app/layout.jsx` — not per page, and
 * deliberately not registered in `mdx-components.js`. It positions itself at the
 * document origin and fades out downward, so one instance covers every route;
 * adding a second from MDX would stack two washes and darken the overlap.
 *
 * `variant="hero"` (default, what the layout uses) is top-weighted and fades
 * downward. `variant="band"` is centred and dissolves on all sides — the CSS
 * supports it for a future mid-page band, but nothing uses it yet.
 */
export const GradientBackdrop = ({ variant = 'hero' }) => (
  <div
    aria-hidden="true"
    className={`rhesis-backdrop${variant === 'band' ? ' rhesis-backdrop--band' : ''}`}
  />
)

export default GradientBackdrop
