'use client'

import React from 'react'

/**
 * ButtonGroup Component
 *
 * A responsive button group for call-to-action links. Colour and shape come
 * from `.btn-rhesis-primary` / `.btn-rhesis-secondary` in globals.css — the
 * black gradient pill from the marketing site — so this component only owns
 * layout.
 *
 * @param {Object} props - Component props
 * @param {string} props.primaryText - Text for primary button
 * @param {string} props.primaryHref - Link for primary button
 * @param {string} props.secondaryText - Text for secondary button
 * @param {string} props.secondaryHref - Link for secondary button
 *
 * Usage:
 * ```jsx
 * <ButtonGroup
 *   primaryText="Get Started →"
 *   primaryHref="/docs/getting-started"
 *   secondaryText="Learn Core Concepts →"
 *   secondaryHref="/docs/concepts"
 * />
 * ```
 */
export const ButtonGroup = ({
  primaryText = 'Get Started →',
  primaryHref = '/docs/getting-started',
  secondaryText = 'Learn Core Concepts →',
  secondaryHref = '/concepts',
}) => (
  <div className="button-group-rhesis">
    <a href={primaryHref} className="btn-rhesis-primary">
      {primaryText}
    </a>
    <a href={secondaryHref} className="btn-rhesis-secondary">
      {secondaryText}
    </a>
  </div>
)

export default ButtonGroup
