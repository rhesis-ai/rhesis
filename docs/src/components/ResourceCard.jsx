'use client'

import React from 'react'

/**
 * ResourceCard Component
 *
 * A squared card component for displaying resources with icon, title, description, and link.
 *
 * @param {Object} props
 * @param {React.ComponentType} props.icon - MUI icon component to display
 * @param {string} props.title - Card title
 * @param {string} props.description - Card description
 * @param {string} props.link - Link URL
 * @param {string} [props.linkText] - Link text with arrow (defaults to "Learn more →")
 *
 * @example
 * ```jsx
 * <ResourceCard
 *   icon={CodeOutlined}
 *   title="Development Setup"
 *   description="Complete guide to setting up your development environment."
 *   link="/docs/development/setup"
 *   linkText="Setup Guide →"
 * />
 * ```
 */
export const ResourceCard = ({ icon: Icon, title, description, link, linkText }) => {
  const cardStyles = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    padding: '1rem',
    border: '1px solid var(--border-color, #e5e7eb)',
    borderRadius: '0.5rem',
    backgroundColor: 'var(--card-bg, #ffffff)',
    transition: 'all 0.2s ease',
    minHeight: '160px',
    position: 'relative',
    textDecoration: 'none',
    color: 'inherit',
    cursor: 'pointer',
  }

  const cardContent = (
    <>
      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '0.375rem',
          backgroundColor: 'var(--primary-bg, rgba(42, 161, 206, 0.1))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '0.75rem',
        }}
      >
        <Icon style={{ fontSize: '20px', color: 'var(--primary-color, #2AA1CE)' }} />
      </div>
      <h3
        style={{
          fontSize: '0.9375rem',
          fontWeight: '600',
          margin: '0 0 0.375rem 0',
          color: 'var(--text-primary, #111827)',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: '0.8125rem',
          color: 'var(--text-secondary, #6B7280)',
          lineHeight: '1.5',
          margin: '0 0 0.75rem 0',
          flex: 1,
        }}
      >
        {description}
      </p>
      <span
        style={{
          fontSize: '0.8125rem',
          color: 'var(--primary-color, #2AA1CE)',
          textDecoration: 'none',
          fontWeight: '500',
        }}
      >
        {linkText || 'Learn more →'}
      </span>
    </>
  )

  return (
    <a
      href={link}
      style={cardStyles}
      className="resource-card"
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--primary-color, #2AA1CE)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(42, 161, 206, 0.15)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border-color, #e5e7eb)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <span
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: 0,
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0, 0, 0, 0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        {title}: {description}
      </span>
      {cardContent}
    </a>
  )
}

export default ResourceCard
