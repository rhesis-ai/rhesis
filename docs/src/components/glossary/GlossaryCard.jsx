'use client'

import React from 'react'
import Link from 'next/link'
import LinkIcon from '@mui/icons-material/Link'
import LabelIcon from '@mui/icons-material/Label'
import glossaryData from '../../../content/glossary/glossary-terms.json'

/**
 * GlossaryCard Component
 *
 * Displays an individual glossary term with its definition, category, related terms, and documentation links.
 * Optimized for both light and dark themes.
 *
 * @param {Object} props - Component props
 * @param {Object} props.term - Term object containing id, term, definition, category, relatedTerms, docLinks, aliases
 */
export const GlossaryCard = ({ term }) => {
  // Helper function to get the actual term name from the glossary data
  const getTermNameById = id => {
    const foundTerm = glossaryData.terms.find(t => t.id === id)
    return foundTerm ? foundTerm.term : id.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
  }
  const cardStyles = {
    padding: '1.25rem',
    border: '1px solid var(--nextra-border)',
    borderRadius: '8px',
    backgroundColor: 'var(--nextra-bg)',
    transition: 'all 0.2s ease',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    textDecoration: 'none',
    color: 'inherit',
  }

  const termTitleStyles = {
    fontSize: '1.25rem',
    fontWeight: '600',
    marginBottom: '0.5rem',
    color: 'var(--nextra-primary-hue)',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  }

  const categoryBadgeStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
    padding: '0.25rem 0.75rem',
    fontSize: '0.75rem',
    fontWeight: '500',
    borderRadius: '12px',
    backgroundColor: 'var(--nextra-primary-hue)',
    color: 'white',
    marginBottom: '0.75rem',
  }

  const definitionStyles = {
    fontSize: '0.95rem',
    lineHeight: '1.6',
    color: 'var(--nextra-content-color)',
    marginBottom: '1rem',
  }

  const sectionTitleStyles = {
    fontSize: '0.85rem',
    fontWeight: '600',
    color: 'var(--nextra-content-color)',
    marginTop: '0.75rem',
    marginBottom: '0.5rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.25rem',
  }

  const linkListStyles = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
    marginBottom: '0.5rem',
  }

  const linkStyles = {
    fontSize: '0.875rem',
    color: 'var(--nextra-primary-hue)',
    textDecoration: 'none',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
    transition: 'opacity 0.2s',
  }

  const relatedTermStyles = {
    fontSize: '0.875rem',
    color: '#0ea5e9',
    textDecoration: 'none',
    padding: '0.375rem 0.75rem',
    borderRadius: '16px',
    backgroundColor: 'rgba(14, 165, 233, 0.1)',
    border: 'none',
    transition: 'all 0.2s',
    cursor: 'pointer',
    display: 'inline-block',
    fontWeight: '500',
  }

  return (
    <Link href={`/glossary/${term.id}`} style={cardStyles} id={term.id}>
      <div>
        <h3 style={termTitleStyles}>{term.term}</h3>

        <div style={categoryBadgeStyles}>
          <LabelIcon style={{ fontSize: '14px' }} />
          {term.category}
        </div>

        <p style={definitionStyles}>{term.definition}</p>

        {term.aliases && term.aliases.length > 0 && (
          <div
            style={{
              fontSize: '0.85rem',
              color: 'var(--nextra-content-secondary)',
              marginBottom: '0.75rem',
            }}
          >
            <em>Also known as: {term.aliases.join(', ')}</em>
          </div>
        )}
      </div>

      <div style={{ marginTop: 'auto' }}>
        {term.docLinks && term.docLinks.length > 0 && (
          <div>
            <div style={sectionTitleStyles}>
              <LinkIcon style={{ fontSize: '16px' }} />
              Documentation
            </div>
            <div style={linkListStyles}>
              {term.docLinks.map((link, index) => (
                <Link 
                  key={index} 
                  href={link} 
                  style={linkStyles}
                  onClick={e => e.stopPropagation()}
                >
                  {link}
                </Link>
              ))}
            </div>
          </div>
        )}

        {term.relatedTerms && term.relatedTerms.length > 0 && (
          <div>
            <div style={sectionTitleStyles}>Related Terms</div>
            <div style={linkListStyles}>
              {term.relatedTerms.map(relatedId => (
                <Link
                  key={relatedId}
                  href={`/glossary/${relatedId}`}
                  style={relatedTermStyles}
                  onClick={e => e.stopPropagation()}
                  onMouseEnter={e => {
                    e.currentTarget.style.backgroundColor = '#0ea5e9'
                    e.currentTarget.style.color = '#ffffff'
                    e.currentTarget.style.transform = 'translateY(-1px)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.backgroundColor = 'rgba(14, 165, 233, 0.1)'
                    e.currentTarget.style.color = '#0ea5e9'
                    e.currentTarget.style.transform = 'translateY(0)'
                  }}
                >
                  {getTermNameById(relatedId)}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </Link>
  )
}

export default GlossaryCard
