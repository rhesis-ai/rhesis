/**
 * GradientBackdrop
 *
 * Soft gradient wash (light) / aurora glow (dark) behind the page, ported from
 * the marketing site's SoftGradientWash and DarkAuroraGlow. All the painting
 * lives in `.rhesis-backdrop` in globals.css.
 *
 * Opt in per page — landing and section-overview pages, not reference pages,
 * where a wash behind body copy costs legibility for nothing. Place it anywhere
 * in the MDX; it positions itself against the viewport.
 *
 * `variant="hero"` (default) is top-weighted and fades downward.
 * `variant="band"` is centred and dissolves on all sides.
 */
export const GradientBackdrop = ({ variant = 'hero' }) => (
  <div
    aria-hidden="true"
    className={`rhesis-backdrop${variant === 'band' ? ' rhesis-backdrop--band' : ''}`}
  />
)

export default GradientBackdrop
