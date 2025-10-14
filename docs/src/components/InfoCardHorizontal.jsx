'use client'

import React from 'react'

/**
 * InfoCardHorizontal Component
 *
 * A horizontally-oriented card component with icon on the left and content on the right.
 * Ideal for feature lists, team capabilities, or use case descriptions.
 *
 * @param {Object} props - Component props
 * @param {React.ComponentType} props.icon - MUI icon component to display
 * @param {string} props.title - Card title/heading
 * @param {string} props.description - Card description text
 * @param {React.ReactNode} [props.children] - Optional custom content instead of description
 * @param {string} [props.className] - Additional CSS classes
 *
 * Usage:
 * ```jsx
 * <InfoCardHorizontal
 *   icon={GroupsOutlined}
 *   title="Collaborative Testing"
 *   description="Bring developers and domain experts together"
 * />
 * ```
 */
export const InfoCardHorizontal = ({
  icon: Icon,
  title,
  description,
  children,
  className = '',
}) => {
  const styles = {
    card: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '1.25rem',
      padding: '1.5rem',
      border: '1px solid',
      borderColor: 'var(--border-color, #e5e7eb)',
      borderRadius: '0.75rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
      transition: 'all 0.2s ease',
      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    },
    iconWrapper: {
      flexShrink: 0,
      width: '3rem',
      height: '3rem',
      borderRadius: '50%',
      backgroundColor: 'var(--icon-bg, #FFF5F0)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    },
    icon: {
      color: 'var(--accent-color, #FD6E12)',
      fontSize: '1.5rem',
    },
    content: {
      flex: 1,
      minWidth: 0,
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: 'var(--text-primary, #3D3D3D)',
      margin: '0 0 0.5rem 0',
      lineHeight: '1.4',
    },
    description: {
      fontSize: '0.9375rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.6',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      margin: '0',
    },
  }

  return (
    <>
      <div
        style={styles.card}
        className={`info-card-horizontal ${className}`}
      >
        <div style={styles.iconWrapper}>
          <Icon style={styles.icon} />
        </div>
        <div style={styles.content}>
          <h3 style={styles.title}>{title}</h3>
          {children || <p style={styles.description}>{description}</p>}
        </div>
      </div>

      <style jsx>{`
        [data-theme='dark'] .info-card-horizontal,
        .dark .info-card-horizontal {
          --border-color: #2c2c2c;
          --card-bg: #161b22;
          --text-primary: #e6edf3;
          --text-secondary: #a9b1bb;
          --accent-color: #fd6e12;
          --icon-bg: rgba(253, 110, 18, 0.1);
        }

        [data-theme='light'] .info-card-horizontal {
          --border-color: #e5e7eb;
          --card-bg: #ffffff;
          --text-primary: #3d3d3d;
          --text-secondary: #6b7280;
          --accent-color: #fd6e12;
          --icon-bg: #fff5f0;
        }

        .info-card-horizontal:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        @media (max-width: 640px) {
          .info-card-horizontal {
            flex-direction: column;
            align-items: center;
            text-align: center;
          }
        }
      `}</style>
    </>
  )
}

export default InfoCardHorizontal
