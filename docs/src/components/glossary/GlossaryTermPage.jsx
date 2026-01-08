'use client'

import React from 'react'
import Link from 'next/link'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import LabelIcon from '@mui/icons-material/Label'
import LinkIcon from '@mui/icons-material/Link'
import glossaryData from '../../../content/glossary/glossary-terms.json'

/**
 * GlossaryTermPage Component
 *
 * Displays an individual glossary term with full details on its own page.
 * Used for SEO-optimized individual term pages.
 *
 * @param {Object} props - Component props
 * @param {string} props.termId - The ID of the term to display
 */
export const GlossaryTermPage = ({ termId }) => {
  const term = glossaryData.terms.find(t => t.id === termId)

  if (!term) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h1>Term Not Found</h1>
        <p>The glossary term you're looking for doesn't exist.</p>
        <Link href="/glossary" style={{ color: '#0ea5e9', textDecoration: 'none' }}>
          ← Back to Glossary
        </Link>
      </div>
    )
  }

  // Helper to get term name from ID
  const getTermNameById = id => {
    const foundTerm = glossaryData.terms.find(t => t.id === id)
    return foundTerm
      ? foundTerm.term
      : id
          .split('-')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ')
  }

  const containerStyles = {
    maxWidth: '800px',
    margin: '0 auto',
  }

  const backLinkStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    color: '#0ea5e9',
    textDecoration: 'none',
    fontSize: '0.875rem',
    marginBottom: '1.5rem',
    transition: 'opacity 0.2s',
    width: 'fit-content',
  }

  const categoryBadgeStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '0.25rem',
    padding: '0.375rem 0.875rem',
    fontSize: '0.8rem',
    fontWeight: '500',
    borderRadius: '12px',
    backgroundColor: 'transparent',
    color: '#0ea5e9',
    border: '1.5px solid #0ea5e9',
    marginBottom: '1.5rem',
    width: 'fit-content',
    textDecoration: 'none',
    transition: 'all 0.2s',
  }

  const definitionStyles = {
    fontSize: '1.125rem',
    lineHeight: '1.7',
    color: 'var(--nextra-content-color)',
    marginBottom: '2rem',
  }

  const aliasesStyles = {
    fontSize: '0.95rem',
    color: 'var(--nextra-content-secondary)',
    fontStyle: 'italic',
    marginBottom: '2rem',
  }

  const sectionTitleStyles = {
    fontSize: '1.25rem',
    fontWeight: '600',
    color: 'var(--nextra-content-color)',
    marginTop: '2.5rem',
    marginBottom: '1rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  }

  const linkListStyles = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  }

  const docLinkStyles = {
    fontSize: '0.95rem',
    color: '#0ea5e9',
    textDecoration: 'none',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.5rem',
    transition: 'opacity 0.2s',
  }

  const relatedTermsGridStyles = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.75rem',
  }

  const relatedTermLinkStyles = {
    fontSize: '0.875rem',
    color: '#0ea5e9',
    textDecoration: 'none',
    padding: '0.5rem 1rem',
    borderRadius: '16px',
    backgroundColor: 'rgba(14, 165, 233, 0.1)',
    fontWeight: '500',
    transition: 'all 0.2s',
    display: 'inline-block',
  }

  return (
    <div style={containerStyles}>
      <Link
        href="/glossary"
        style={backLinkStyles}
        onMouseEnter={e => (e.currentTarget.style.opacity = '0.7')}
        onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
      >
        <ArrowBackIcon style={{ fontSize: '18px' }} />
        Back to Glossary
      </Link>

      <Link
        href={`/glossary?category=${encodeURIComponent(term.category)}`}
        style={categoryBadgeStyles}
        onMouseEnter={e => {
          e.currentTarget.style.backgroundColor = '#0ea5e9'
          e.currentTarget.style.color = '#ffffff'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.backgroundColor = 'transparent'
          e.currentTarget.style.color = '#0ea5e9'
        }}
      >
        <LabelIcon style={{ fontSize: '14px' }} />
        {term.category}
      </Link>

      <p style={definitionStyles}>{term.definition}</p>

      {term.aliases && term.aliases.length > 0 && (
        <div style={aliasesStyles}>Also known as: {term.aliases.join(', ')}</div>
      )}

      {term.docLinks && term.docLinks.length > 0 && (
        <div>
          <h2 style={sectionTitleStyles}>
            <LinkIcon style={{ fontSize: '20px' }} />
            Documentation
          </h2>
          <div style={linkListStyles}>
            {term.docLinks.map(link => (
              <Link
                key={link}
                href={link}
                style={docLinkStyles}
                onMouseEnter={e => (e.currentTarget.style.opacity = '0.7')}
                onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
              >
                <LinkIcon style={{ fontSize: '16px' }} />
                {link}
              </Link>
            ))}
          </div>
        </div>
      )}

      {term.relatedTerms && term.relatedTerms.length > 0 && (
        <div>
          <h2 style={sectionTitleStyles}>Related Terms</h2>
          <div style={relatedTermsGridStyles}>
            {term.relatedTerms.map(relatedId => (
              <Link
                key={relatedId}
                href={`/glossary/${relatedId}`}
                style={relatedTermLinkStyles}
                onMouseEnter={e => {
                  e.currentTarget.style.backgroundColor = '#0ea5e9'
                  e.currentTarget.style.color = '#ffffff'
                  e.currentTarget.style.transform = 'translateY(-2px)'
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
  )
}

export default GlossaryTermPage
