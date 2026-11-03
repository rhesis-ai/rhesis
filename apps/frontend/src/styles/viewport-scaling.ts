/**
 * Helpers for the root zoom ladder defined in `viewport-scaling.css`.
 *
 * CSS `zoom` scales layout. In Chromium `vh`/`vw` are *not* divided by the
 * zoom factor, so inside the zoomed subtree a plain `height: 100vh` gets
 * painted at 85% of the viewport, leaving a visible dead strip. Safari divides
 * them itself, so dividing again there overshoots. `--ui-vh-scale` is the
 * zoom in the first case and 1 in the second; `VH_ZOOM_PROBE_SCRIPT` decides.
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
 * scaledVh()                       // calc(100vh / var(--ui-vh-scale, 1))
 * scaledVh(70)                     // calc(70vh / var(--ui-vh-scale, 1))
 * `calc(${scaledVh()} - 210px)`    // viewport minus 210px of chrome
 */
export const scaledVh = (vh = 100) => `calc(${vh}vh / var(--ui-vh-scale, 1))`;

/** As {@link scaledVh}, for viewport widths. */
export const scaledVw = (vw = 100) => `calc(${vw}vw / var(--ui-vh-scale, 1))`;

/**
 * Inline <head> script, run before first paint: sets `data-vh-zoom-aware` on
 * <html> when the browser already compensates viewport units for `zoom`.
 *
 * Compares a `100vh` box with an `innerHeight`px box under the same zoom, so
 * it holds whether `getBoundingClientRect` reports zoomed px (Chromium) or
 * unzoomed CSS px (Safari): the ratio is 1 without compensation, 1/zoom with.
 * Without `zoom` support the ratio is also 1, which is right — no zoom, no
 * compensation needed.
 */
export const VH_ZOOM_PROBE_SCRIPT = `(function(){try{
var d=document.documentElement,s='position:absolute;visibility:hidden;pointer-events:none;top:0;left:0;width:1px;zoom:0.5;height:';
var a=document.createElement('div'),b=document.createElement('div');
a.style.cssText=s+'100vh';b.style.cssText=s+window.innerHeight+'px';
d.appendChild(a);d.appendChild(b);
var r=a.getBoundingClientRect().height/b.getBoundingClientRect().height;
d.removeChild(a);d.removeChild(b);
if(r>1.5)d.setAttribute('data-vh-zoom-aware','');
}catch(e){}})();`;
