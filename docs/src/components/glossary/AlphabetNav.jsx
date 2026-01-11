'use client'

import React from 'react'

/**
 * AlphabetNav Component
 *
 * A-Z navigation bar for quickly jumping to glossary terms by first letter.
 * Highlights letters that have available terms.
 *
 * @param {Object} props - Component props
 * @param {string[]} props.availableLetters - Array of letters that have terms
 * @param {string} props.activeLetter - Currently active letter
 * @param {Function} props.onLetterClick - Callback when a letter is clicked
 */
export const AlphabetNav = ({ availableLetters = [], activeLetter, onLetterClick }) => {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

  const containerStyles = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
    justifyContent: 'center',
    marginBottom: '2rem',
    padding: '1rem',
    borderRadius: '8px',
    backgroundColor: 'var(--nextra-bg-secondary)',
  }

  const letterButtonBaseStyles = {
    width: '2.5rem',
    height: '2.5rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: 'none',
    borderRadius: '4px',
    fontSize: '0.875rem',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.2s',
    background: 'none',
  }

  const getLetterStyles = letter => {
    const isAvailable = availableLetters.includes(letter)
    const isActive = activeLetter === letter

    if (!isAvailable) {
      return {
        ...letterButtonBaseStyles,
        color: 'var(--nextra-content-disabled)',
        cursor: 'not-allowed',
        opacity: 0.4,
      }
    }

    if (isActive) {
      return {
        ...letterButtonBaseStyles,
        backgroundColor: 'var(--nextra-primary-hue)',
        color: 'white',
      }
    }

    return {
      ...letterButtonBaseStyles,
      color: 'var(--nextra-primary-hue)',
    }
  }

  const handleLetterClick = letter => {
    if (availableLetters.includes(letter)) {
      onLetterClick(letter)

      // Smooth scroll to the letter section
      const element = document.getElementById(`letter-${letter}`)
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
  }

  return (
    <nav style={containerStyles} aria-label="Alphabet navigation">
      {alphabet.map(letter => {
        const isAvailable = availableLetters.includes(letter)
        return (
          <button
            key={letter}
            onClick={() => handleLetterClick(letter)}
            style={getLetterStyles(letter)}
            disabled={!isAvailable}
            aria-label={`Jump to letter ${letter}`}
            aria-current={activeLetter === letter ? 'true' : undefined}
            onMouseEnter={e => {
              if (isAvailable && activeLetter !== letter) {
                e.currentTarget.style.backgroundColor = 'var(--nextra-primary-hue-light)'
              }
            }}
            onMouseLeave={e => {
              if (activeLetter !== letter) {
                e.currentTarget.style.backgroundColor = 'transparent'
              }
            }}
          >
            {letter}
          </button>
        )
      })}
    </nav>
  )
}

export default AlphabetNav
