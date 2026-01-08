'use client'

import React from 'react'
import InfoIcon from '@mui/icons-material/Info'
import GlossaryCard from './GlossaryCard'

/**
 * GlossaryGrid Component
 *
 * Organizes glossary terms alphabetically with section headers.
 * Displays terms in a responsive grid layout and handles empty states.
 *
 * @param {Object} props - Component props
 * @param {Array} props.terms - Array of term objects to display
 * @param {Array} props.categories - Available categories for filtering
 * @param {string} props.selectedCategory - Currently selected category filter
 * @param {Function} props.onCategoryChange - Callback when category filter changes
 */
export const GlossaryGrid = ({
  terms,
  categories,
  selectedCategory,
  onCategoryChange,
}) => {
  // Group terms by first letter
  const groupedTerms = terms.reduce((acc, term) => {
    const firstLetter = term.term.charAt(0).toUpperCase()
    if (!acc[firstLetter]) {
      acc[firstLetter] = []
    }
    acc[firstLetter].push(term)
    return acc
  }, {})

  // Sort letters alphabetically
  const sortedLetters = Object.keys(groupedTerms).sort()

  const categoryFilterStyles = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
    marginBottom: '1.5rem',
    alignItems: 'center',
  }

  const categoryLabelStyles = {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: 'var(--nextra-content-color)',
    marginRight: '0.5rem',
  }

  const categoryChipStyles = isSelected => ({
    padding: '0.5rem 1rem',
    fontSize: '0.875rem',
    fontWeight: '500',
    borderRadius: '20px',
    border: '1px solid var(--nextra-border)',
    backgroundColor: isSelected ? 'var(--nextra-primary-hue)' : 'var(--nextra-bg)',
    color: isSelected ? 'white' : 'var(--nextra-content-color)',
    cursor: 'pointer',
    transition: 'all 0.2s',
  })

  const letterSectionStyles = {
    marginBottom: '3rem',
  }

  const letterHeaderStyles = {
    fontSize: '2rem',
    fontWeight: '700',
    color: 'var(--nextra-primary-hue)',
    marginBottom: '1rem',
    paddingBottom: '0.5rem',
    borderBottom: '2px solid var(--nextra-border)',
  }

  const gridStyles = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '1.5rem',
    marginBottom: '2rem',
  }

  const emptyStateStyles = {
    textAlign: 'center',
    padding: '3rem 1rem',
    color: 'var(--nextra-content-secondary)',
  }

  const emptyStateIconStyles = {
    fontSize: '3rem',
    marginBottom: '1rem',
    opacity: 0.5,
  }

  if (terms.length === 0) {
    return (
      <div style={emptyStateStyles}>
        <InfoIcon style={emptyStateIconStyles} />
        <p style={{ fontSize: '1.125rem', marginBottom: '0.5rem' }}>No terms found</p>
        <p style={{ fontSize: '0.875rem' }}>Try adjusting your search or filter criteria</p>
      </div>
    )
  }

  return (
    <div>
      {categories && categories.length > 0 && (
        <div style={categoryFilterStyles}>
          <span style={categoryLabelStyles}>Filter by category:</span>
          <button
            onClick={() => onCategoryChange(null)}
            style={categoryChipStyles(!selectedCategory)}
            onMouseEnter={e => {
              if (selectedCategory) {
                e.currentTarget.style.backgroundColor = 'var(--nextra-bg-secondary)'
              }
            }}
            onMouseLeave={e => {
              if (selectedCategory) {
                e.currentTarget.style.backgroundColor = 'var(--nextra-bg)'
              }
            }}
          >
            All
          </button>
          {categories.map(category => (
            <button
              key={category}
              onClick={() => onCategoryChange(category)}
              style={categoryChipStyles(selectedCategory === category)}
              onMouseEnter={e => {
                if (selectedCategory !== category) {
                  e.currentTarget.style.backgroundColor = 'var(--nextra-bg-secondary)'
                }
              }}
              onMouseLeave={e => {
                if (selectedCategory !== category) {
                  e.currentTarget.style.backgroundColor = 'var(--nextra-bg)'
                }
              }}
            >
              {category}
            </button>
          ))}
        </div>
      )}

      {sortedLetters.map(letter => (
        <div key={letter} id={`letter-${letter}`} style={letterSectionStyles}>
          <h2 style={letterHeaderStyles}>{letter}</h2>
          <div style={gridStyles}>
            {groupedTerms[letter].map(term => (
              <GlossaryCard key={term.id} term={term} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default GlossaryGrid
