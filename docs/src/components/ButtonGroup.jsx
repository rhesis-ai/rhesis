'use client'

import React from 'react'

/**
 * ButtonGroup Component
 *
 * A responsive button group for call-to-action links.
 * Ensures proper styling in both light and dark themes.
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
 *   primaryHref="/getting-started"
 *   secondaryText="Learn Core Concepts →"
 *   secondaryHref="/getting-started/concepts"
 * />
 * ```
 */
export const ButtonGroup = ({
  primaryText = 'Get Started →',
  primaryHref = '/getting-started',
  secondaryText = 'Learn Core Concepts →',
  secondaryHref = '/getting-started/concepts',
}) => {
  const styles = {
    container: {
      display: 'flex',
      flexDirection: 'row',
      gap: '0.75rem',
      margin: '1.5rem 0',
      flexWrap: 'wrap',
    },
    primaryButton: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '0.5rem 1rem',
      border: 'none',
      backgroundColor: '#2AA1CE',
      color: 'white',
      fontSize: '0.875rem',
      fontWeight: '500',
      borderRadius: '0.375rem',
      textDecoration: 'none',
      transition: 'all 0.2s ease-in-out',
      cursor: 'pointer',
      fontFamily: 'Be Vietnam Pro, sans-serif',
    },
    secondaryButton: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '0.5rem 1rem',
      border: '1px solid #2AA1CE',
      backgroundColor: 'var(--secondary-btn-bg, #ffffff)',
      color: 'var(--secondary-btn-color, #3D3D3D)',
      fontSize: '0.875rem',
      fontWeight: '500',
      borderRadius: '0.375rem',
      textDecoration: 'none',
      transition: 'all 0.2s ease-in-out',
      cursor: 'pointer',
      fontFamily: 'Be Vietnam Pro, sans-serif',
    },
  }

  return (
    <>
      <div style={styles.container} className="button-group-rhesis">
        <a
          href={primaryHref}
          style={styles.primaryButton}
          className="btn-primary-rhesis"
        >
          {primaryText}
        </a>
        <a
          href={secondaryHref}
          style={styles.secondaryButton}
          className="btn-secondary-rhesis"
        >
          {secondaryText}
        </a>
      </div>

      <style jsx>{`
        .btn-primary-rhesis:hover {
          background-color: #3bc4f2 !important;
        }

        .btn-secondary-rhesis:hover {
          background-color: var(--secondary-btn-hover-bg, #f2f9fd) !important;
          color: #2aa1ce !important;
        }

        [data-theme='dark'] .button-group-rhesis {
          --secondary-btn-bg: #161b22;
          --secondary-btn-color: #e6edf3;
          --secondary-btn-hover-bg: #1f242b;
        }

        [data-theme='light'] .button-group-rhesis {
          --secondary-btn-bg: #ffffff;
          --secondary-btn-color: #3d3d3d;
          --secondary-btn-hover-bg: #f2f9fd;
        }

        @media (max-width: 640px) {
          .button-group-rhesis {
            flex-direction: column;
          }

          .btn-primary-rhesis,
          .btn-secondary-rhesis {
            width: 100%;
          }
        }
      `}</style>
    </>
  )
}

export default ButtonGroup
