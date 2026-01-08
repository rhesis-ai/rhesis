'use client'

import React, { useState, useEffect } from 'react'
import SearchIcon from '@mui/icons-material/Search'
import ClearIcon from '@mui/icons-material/Clear'

/**
 * GlossarySearch Component
 *
 * Real-time search input with debouncing for filtering glossary terms.
 * Searches across term names, definitions, and aliases.
 *
 * @param {Object} props - Component props
 * @param {string} props.searchTerm - Current search term
 * @param {Function} props.onSearchChange - Callback when search term changes
 */
export const GlossarySearch = ({ searchTerm, onSearchChange }) => {
  const [localSearchTerm, setLocalSearchTerm] = useState(searchTerm)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearchChange(localSearchTerm)
    }, 300)

    return () => clearTimeout(timer)
  }, [localSearchTerm, onSearchChange])

  const handleClear = () => {
    setLocalSearchTerm('')
    onSearchChange('')
  }

  const containerStyles = {
    position: 'relative',
    marginBottom: '1.5rem',
    maxWidth: '600px',
  }

  const inputWrapperStyles = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  }

  const searchIconStyles = {
    position: 'absolute',
    left: '1rem',
    color: 'var(--nextra-content-secondary)',
    pointerEvents: 'none',
    display: 'flex',
    alignItems: 'center',
  }

  const inputStyles = {
    width: '100%',
    padding: '0.75rem 3rem 0.75rem 3rem',
    fontSize: '1rem',
    border: '1px solid var(--nextra-border)',
    borderRadius: '8px',
    backgroundColor: 'var(--nextra-bg)',
    color: 'var(--nextra-content-color)',
    outline: 'none',
    transition: 'border-color 0.2s',
  }

  const clearButtonStyles = {
    position: 'absolute',
    right: '0.75rem',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '0.25rem',
    display: 'flex',
    alignItems: 'center',
    color: 'var(--nextra-content-secondary)',
    transition: 'color 0.2s',
  }

  return (
    <div style={containerStyles}>
      <div style={inputWrapperStyles}>
        <div style={searchIconStyles}>
          <SearchIcon />
        </div>
        <input
          type="text"
          value={localSearchTerm}
          onChange={e => setLocalSearchTerm(e.target.value)}
          placeholder="Search terms, definitions, or aliases..."
          style={inputStyles}
          aria-label="Search glossary terms"
          onFocus={e => {
            e.target.style.borderColor = 'var(--nextra-primary-hue)'
          }}
          onBlur={e => {
            e.target.style.borderColor = 'var(--nextra-border)'
          }}
        />
        {localSearchTerm && (
          <button
            onClick={handleClear}
            style={clearButtonStyles}
            aria-label="Clear search"
            onMouseEnter={e => {
              e.currentTarget.style.color = 'var(--nextra-primary-hue)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'var(--nextra-content-secondary)'
            }}
          >
            <ClearIcon />
          </button>
        )}
      </div>
    </div>
  )
}

export default GlossarySearch

