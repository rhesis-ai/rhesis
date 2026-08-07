/**
 * NavLogo
 *
 * Navbar brand lockup — the logo mark plus a "Rhesis AI" wordmark in Sora
 * ExtraBold, matching the marketing site's header (Figma 2351:1671).
 *
 * Replaces the previous theme-swapped PNG pair: the mark is coloured brand
 * artwork that reads on either canvas, and the wordmark takes its colour from
 * `--rh-heading`, so there is nothing left to switch on the active theme and no
 * hydration guard needed.
 */
export const NavLogo = () => (
  <span className="rhesis-navlogo">
    <img src="/logo/rhesis-mark.svg" alt="" width={34} height={22} />
    <span className="rhesis-navlogo__word">Rhesis AI</span>
  </span>
)

export default NavLogo
