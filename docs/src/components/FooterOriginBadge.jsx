/**
 * Footer origin mark — German flag centred in an EU star ring, no card frame.
 * Ported from the marketing site's FooterOriginBadge.
 */

const STAR = 'M0-2.15.645-.66 2.15-.66.93.29 1.36 1.85 0 .93-1.36 1.85-.93.29-2.15-.66-.645-.66z'

/** Flag centre in the 85×56 viewBox (26×18 flag at 29.5,19) */
const FLAG_CX = 42.5
const FLAG_CY = 28
const STAR_RADIUS = 22

const stars = Array.from({ length: 12 }, (_, index) => {
  const angle = ((index * 30 - 90) * Math.PI) / 180
  return {
    key: index,
    x: FLAG_CX + Math.cos(angle) * STAR_RADIUS,
    y: FLAG_CY + Math.sin(angle) * STAR_RADIUS,
  }
})

export const FooterOriginBadge = () => (
  <div className="rhesis-footer__origin" role="img" aria-label="Developed in DE. Hosted in EU.">
    <svg
      aria-hidden="true"
      className="rhesis-footer__origin-svg"
      fill="none"
      viewBox="0 0 85 56"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clipPath="url(#footer-origin-de-flag)">
        <rect fill="#000000" height="18" width="26" x="29.5" y="19" />
        <rect fill="#DD0000" height="6" width="26" x="29.5" y="25" />
        <rect fill="#FFCE00" height="6" width="26" x="29.5" y="31" />
      </g>
      {/* On dark the black band melts into the footer — ring the flag instead */}
      <rect
        className="rhesis-footer__origin-ring"
        fill="none"
        height="18"
        rx="1.5"
        strokeWidth="1"
        width="26"
        x="29.5"
        y="19"
      />
      <defs>
        <clipPath id="footer-origin-de-flag">
          <rect height="18" rx="1.5" width="26" x="29.5" y="19" />
        </clipPath>
      </defs>
      {stars.map(({ key, x, y }) => (
        <path
          key={key}
          className="rhesis-footer__origin-star"
          d={STAR}
          transform={`translate(${x} ${y})`}
        />
      ))}
    </svg>

    <div className="rhesis-footer__origin-text">
      <span>Developed in DE</span>
      <span>Hosted in EU</span>
    </div>
  </div>
)

export default FooterOriginBadge
