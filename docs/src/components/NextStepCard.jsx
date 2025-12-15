'use client'

import React from 'react'

/**
 * NextStepCard Component
 *
 * A compact card component for "Next Steps" sections.
 * Features emoji icons, horizontal layout, and hover effects.
 *
 * @param {Object} props - Component props
 * @param {string} props.emoji - Emoji to display
 * @param {string} props.title - Card title
 * @param {string} props.description - Card description text
 * @param {string} props.link - Link URL
 * @param {string} props.linkText - Link text
 * @param {boolean} [props.external] - Whether link is external
 *
 * Usage:
 * ```jsx
 * <NextStepCard
 *   emoji="📚"
 *   title="Core Concepts"
 *   description="Understand the fundamental concepts of Gen AI testing with Rhesis."
 *   link="/getting-started/concepts"
 *   linkText="Learn Core Concepts →"
 * />
 * ```
 */
export const NextStepCard = ({ emoji, title, description, link, linkText, external = false }) => {
  const [isHovered, setIsHovered] = React.useState(false)

  const styles = {
    card: {
      display: 'block',
      padding: '1.25rem',
      border: '1px solid',
      borderColor: isHovered ? '#2AA1CE' : 'var(--border-color, #e5e7eb)',
      borderRadius: '0.75rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
      transition: 'all 0.2s ease',
      textDecoration: 'none',
      boxShadow: isHovered
        ? '0 4px 12px rgba(42, 161, 206, 0.12)'
        : '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
      transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
      cursor: 'pointer',
    },
    content: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '1rem',
    },
    emojiWrapper: {
      fontSize: '2rem',
      lineHeight: 1,
      flexShrink: 0,
    },
    textContent: {
      flex: 1,
      minWidth: 0,
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: isHovered ? '#2AA1CE' : 'var(--text-primary, #3D3D3D)',
      margin: '0 0 0.5rem 0',
      transition: 'color 0.2s ease',
    },
    description: {
      fontSize: '0.875rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.6',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      margin: '0 0 0.75rem 0',
    },
    link: {
      color: '#2AA1CE',
      textDecoration: 'none',
      fontWeight: '500',
      fontSize: '0.875rem',
      transition: 'transform 0.2s ease',
      display: 'inline-block',
      transform: isHovered ? 'translateX(4px)' : 'translateX(0)',
    },
  }

  return (
    <a
      href={link}
      target={external ? '_blank' : '_self'}
      rel={external ? 'noopener noreferrer' : undefined}
      style={styles.card}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="next-step-card"
    >
      <div style={styles.content}>
        <span style={styles.emojiWrapper}>{emoji}</span>
        <div style={styles.textContent}>
          <h3 style={styles.title}>{title}</h3>
          <p style={styles.description}>{description}</p>
          <span style={styles.link}>{linkText}</span>
        </div>
      </div>
    </a>
  )
}

/**
 * NextStepCardGrid Component
 *
 * A responsive grid wrapper for NextStepCard components.
 */
export const NextStepCardGrid = ({ children }) => {
  const styles = {
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
      gap: '1rem',
      marginTop: '1.5rem',
      marginBottom: '2rem',
    },
  }

  return (
    <div style={styles.grid} className="next-step-card-grid">
      {children}
    </div>
  )
}

export default NextStepCard

