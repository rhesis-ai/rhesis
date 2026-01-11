'use client'

import Link from 'next/link'

/**
 * InteractiveLink - Client component for links with hover effects
 */
export const InteractiveLink = ({ href, style, hoverStyle, children, ...props }) => {
  return (
    <Link
      href={href}
      style={style}
      onMouseEnter={e => {
        if (hoverStyle) {
          Object.assign(e.currentTarget.style, hoverStyle)
        }
      }}
      onMouseLeave={e => {
        if (style) {
          Object.assign(e.currentTarget.style, style)
        }
      }}
      {...props}
    >
      {children}
    </Link>
  )
}
