'use client'

import React from 'react'

/**
 * InfoCard Component
 *
 * A reusable card component with consistent styling for displaying features,
 * examples, or other informational content with icons.
 *
 * @param {Object} props - Component props
 * @param {React.ComponentType} props.icon - MUI icon component to display
 * @param {string} props.title - Card title
 * @param {string} props.description - Card description text
 * @param {string} [props.link] - Optional link URL
 * @param {string} [props.linkText] - Optional link text
 * @param {boolean} [props.external] - Whether link is external
 * @param {React.ReactNode} [props.children] - Optional custom content instead of description
 * @param {string} [props.className] - Additional CSS classes
 *
 * Usage:
 * ```jsx
 * <InfoCard
 *   icon={ScienceOutlined}
 *   title="Test Generation"
 *   description="Automated scenario creation at scale"
 * />
 * ```
 */
export const InfoCard = ({
  icon: Icon,
  title,
  description,
  link,
  linkText,
  external = false,
  children,
  className = '',
}) => {
  const hasLink = Boolean(link)

  const styles = {
    card: {
      textAlign: 'center',
      padding: '1.5rem',
      border: '1px solid',
      borderColor: 'var(--border-color, #e5e7eb)',
      borderRadius: '0.75rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
      transition: hasLink ? 'all 0.2s ease' : 'none',
      cursor: 'default',
      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    },
    iconWrapper: {
      width: '2.5rem',
      height: '2.5rem',
      borderRadius: '50%',
      backgroundColor: 'var(--icon-bg, #FFF5F0)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 0.75rem auto',
    },
    icon: {
      color: 'var(--accent-color, #FD6E12)',
      fontSize: '1.25rem',
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: 'var(--text-primary, #3D3D3D)',
      margin: '0 0 0.75rem 0',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.5rem',
    },
    arrowIcon: {
      fontSize: '1rem',
      color: 'var(--text-tertiary, #9CA3AF)',
    },
    description: {
      fontSize: '0.875rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.6',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      margin: hasLink ? '0 0 1rem 0' : '0',
    },
    link: {
      color: '#2AA1CE',
      textDecoration: 'none',
      fontWeight: '500',
      fontSize: '0.875rem',
      transition: 'color 0.2s ease',
    },
  }

  const CardContent = () => (
    <>
      <div style={styles.iconWrapper}>
        <Icon style={styles.icon} />
      </div>
      <h3 style={styles.title}>
        {title}
        {hasLink && <span style={styles.arrowIcon}>↗</span>}
      </h3>
      {children || <p style={styles.description}>{description}</p>}
      {hasLink && (
        <a
          href={link}
          target={external ? '_blank' : '_self'}
          rel={external ? 'noopener noreferrer' : undefined}
          style={styles.link}
          className="info-card-link"
        >
          {linkText}
        </a>
      )}
    </>
  )

  return (
    <>
      <div
        style={styles.card}
        className={`info-card ${hasLink ? 'info-card-linked' : ''} ${className}`}
      >
        <CardContent />
      </div>

      <style jsx>{`
        [data-theme='dark'] .info-card {
          --border-color: #30363d;
          --card-bg: #161b22;
          --text-primary: #e6edf3;
          --text-secondary: #a9b1bb;
          --text-tertiary: #6b7280;
          --accent-color: #fd6e12;
          --icon-bg: rgba(253, 110, 18, 0.1);
        }

        [data-theme='light'] .info-card {
          --border-color: #e5e7eb;
          --card-bg: #ffffff;
          --text-primary: #3d3d3d;
          --text-secondary: #6b7280;
          --text-tertiary: #9ca3af;
          --accent-color: #fd6e12;
          --icon-bg: #fff5f0;
        }

        .info-card-linked:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }

        .info-card-link:hover {
          color: #3bc4f2;
        }
      `}</style>
    </>
  )
}

export default InfoCard
