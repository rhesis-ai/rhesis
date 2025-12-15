'use client'

import React from 'react'

/**
 * PathCard Component
 *
 * A visually appealing card component for the "Choose Your Path" section.
 * Features large emoji icons, hover effects, and clear call-to-action links.
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
 * <PathCard
 *   emoji="☁️"
 *   title="Cloud Platform"
 *   description="Start testing immediately with zero setup required."
 *   link="https://app.rhesis.ai"
 *   linkText="Go to app.rhesis.ai →"
 *   external
 * />
 * ```
 */
export const PathCard = ({ emoji, title, description, link, linkText, external = false }) => {
  const [isHovered, setIsHovered] = React.useState(false)

  const styles = {
    card: {
      display: 'block',
      padding: '2rem 1.5rem',
      border: '1px solid',
      borderColor: isHovered ? '#2AA1CE' : 'var(--border-color, #e5e7eb)',
      borderRadius: '0.75rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
      transition: 'all 0.25s ease',
      textDecoration: 'none',
      textAlign: 'center',
      boxShadow: isHovered
        ? '0 10px 25px rgba(42, 161, 206, 0.15)'
        : '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
      transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
      cursor: 'pointer',
    },
    emojiWrapper: {
      fontSize: '3rem',
      lineHeight: 1,
      marginBottom: '1rem',
      display: 'block',
    },
    title: {
      fontSize: '1.25rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: isHovered ? '#2AA1CE' : 'var(--text-primary, #3D3D3D)',
      margin: '0 0 0.75rem 0',
      transition: 'color 0.2s ease',
    },
    description: {
      fontSize: '0.9375rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.6',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      margin: '0 0 1.25rem 0',
    },
    link: {
      color: '#2AA1CE',
      textDecoration: 'none',
      fontWeight: '500',
      fontSize: '0.9375rem',
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
      className="path-card"
    >
      <span style={styles.emojiWrapper}>{emoji}</span>
      <h3 style={styles.title}>{title}</h3>
      <p style={styles.description}>{description}</p>
      <span style={styles.link}>{linkText}</span>
    </a>
  )
}

/**
 * PathCardGrid Component
 *
 * A responsive grid wrapper for PathCard components.
 */
export const PathCardGrid = ({ children }) => {
  const styles = {
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: '1.5rem',
      marginTop: '1.5rem',
      marginBottom: '2rem',
    },
  }

  return (
    <div style={styles.grid} className="path-card-grid">
      {children}
    </div>
  )
}

export default PathCard

