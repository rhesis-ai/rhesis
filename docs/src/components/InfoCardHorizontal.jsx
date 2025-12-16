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
 * @param {string} [props.link] - Optional link URL
 * @param {string} [props.linkText] - Optional link text
 * @param {boolean} [props.external] - Whether link is external
 * @param {React.ReactNode} [props.children] - Optional custom content instead of description
 * @param {string} [props.className] - Additional CSS classes
 *
 * Usage:
 * ```jsx
 * <InfoCardHorizontal
 *   icon={GroupsOutlined}
 *   title="Collaborative Testing"
 *   description="Bring developers and domain experts together"
 *   link="/docs/features"
 *   linkText="Learn More →"
 * />
 * ```
 */
export const InfoCardHorizontal = ({
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
      textDecoration: 'none',
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
      margin: hasLink ? '0 0 0.75rem 0' : '0',
    },
    link: {
      color: '#2AA1CE',
      textDecoration: 'none',
      fontWeight: '500',
      fontSize: '0.875rem',
      transition: 'color 0.2s ease',
      display: 'inline-block',
    },
  }

  const cardContent = (
    <>
      <div style={styles.iconWrapper}>
        <Icon style={styles.icon} />
      </div>
      <div style={styles.content}>
        <h3 style={styles.title}>{title}</h3>
        {children || <p style={styles.description}>{description}</p>}
        {hasLink && (
          <span style={styles.link}>
            {linkText || 'Learn more →'}
          </span>
        )}
      </div>
    </>
  )

  if (hasLink) {
    return (
      <a
        href={link}
        target={external ? '_blank' : '_self'}
        rel={external ? 'noopener noreferrer' : undefined}
        style={{
          ...styles.card,
          textDecoration: 'none',
          color: 'inherit',
          cursor: 'pointer',
        }}
        className={`info-card-horizontal ${className}`}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
          e.currentTarget.style.transform = 'translateY(-2px)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
          e.currentTarget.style.transform = 'translateY(0)'
        }}
      >
        {cardContent}
      </a>
    )
  }

  return (
    <div style={styles.card} className={`info-card-horizontal ${className}`}>
      {cardContent}
    </div>
  )
}

export default InfoCardHorizontal
