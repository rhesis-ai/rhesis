/**
 * Helpers for the root zoom ladder defined in `viewport-scaling.css`.
 *
 * CSS `zoom` scales layout, but `vh`/`vw` are resolved against the real
 * viewport and are *not* divided by the zoom factor. So inside the zoomed
 * subtree a plain `height: 100vh` resolves to the full viewport in CSS px and
 * then gets painted at 85% of it, leaving a visible dead strip.
 *
 * Only elements **inside** `[data-ui-scale-root]` need this. Surfaces that MUI
 * portals to `document.body` — Dialog/Drawer `PaperProps`, Popover, Menu,
 * Tooltip, Snackbar — are outside the zoomed subtree and render at zoom 1, so
 * their viewport units are already correct and must be left alone.
 */

/**
 * A viewport-height expression compensated for the zoom ladder.
 *
 * Divide the viewport term and only the viewport term: a companion px offset
 * is itself scaled by the zoom, so it must stay outside the division.
 *
 * @example
 * scaledVh()                       // calc(100vh / var(--ui-scale, 1))
 * scaledVh(70)                     // calc(70vh / var(--ui-scale, 1))
 * `calc(${scaledVh()} - 210px)`    // viewport minus 210px of chrome
 */
export const scaledVh = (vh = 100) => `calc(${vh}vh / var(--ui-scale, 1))`;

/** As {@link scaledVh}, for viewport widths. */
export const scaledVw = (vw = 100) => `calc(${vw}vw / var(--ui-scale, 1))`;
