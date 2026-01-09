'use client'

import React, { useState, useMemo, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import GlossarySearch from './GlossarySearch'
import AlphabetNav from './AlphabetNav'
import GlossaryGrid from './GlossaryGrid'
import glossaryDataRaw from '../../../content/glossary/glossary-terms.jsonl'

// Parse JSONL format (one JSON object per line)
const glossaryData = {
  terms: glossaryDataRaw
    .trim()
    .split('\n')
    .map(line => JSON.parse(line)),
}

/**
 * GlossaryPage Component
 *
 * Main container component for the glossary feature.
 * Manages search, filter state, and integrates all glossary sub-components.
 *
 * @param {Object} props - Component props
 */
export const GlossaryPage = () => {
  const searchParams = useSearchParams()
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [activeLetter, setActiveLetter] = useState(null)

  // Memoize terms to prevent unnecessary re-renders
  const terms = useMemo(() => glossaryData.terms || [], [])

  // Read category from URL parameters on mount
  useEffect(() => {
    const categoryParam = searchParams.get('category')
    if (categoryParam) {
      setSelectedCategory(categoryParam)
    }
  }, [searchParams])

  // Get unique categories
  const categories = useMemo(() => {
    const uniqueCategories = [...new Set(terms.map(term => term.category))]
    return uniqueCategories.sort()
  }, [terms])

  // Filter terms based on search and category
  const filteredTerms = useMemo(() => {
    let filtered = terms

    // Apply search filter
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase()
      filtered = filtered.filter(
        term =>
          term.term.toLowerCase().includes(searchLower) ||
          term.definition.toLowerCase().includes(searchLower) ||
          (term.aliases && term.aliases.some(alias => alias.toLowerCase().includes(searchLower)))
      )
    }

    // Apply category filter
    if (selectedCategory) {
      filtered = filtered.filter(term => term.category === selectedCategory)
    }

    // Sort alphabetically
    return filtered.sort((a, b) => a.term.localeCompare(b.term))
  }, [terms, searchTerm, selectedCategory])

  // Get available letters (letters that have terms)
  const availableLetters = useMemo(() => {
    const letters = new Set(filteredTerms.map(term => term.term.charAt(0).toUpperCase()))
    return Array.from(letters).sort()
  }, [filteredTerms])

  const statsStyles = {
    fontSize: '0.875rem',
    color: 'var(--nextra-content-secondary)',
    marginTop: '1.5rem',
    marginBottom: '2rem',
  }

  return (
    <div className="glossary-page" style={{ marginTop: '1.5rem' }}>
      <p>
        A comprehensive reference of terms and concepts used throughout the Rhesis platform. Use the
        search bar or alphabet navigation to find specific terms.
      </p>

      <div style={statsStyles}>
        Showing {filteredTerms.length} of {terms.length} terms
        {selectedCategory && ` in ${selectedCategory}`}
        {searchTerm && ` matching "${searchTerm}"`}
      </div>

      <GlossarySearch searchTerm={searchTerm} onSearchChange={setSearchTerm} />

      <AlphabetNav
        availableLetters={availableLetters}
        activeLetter={activeLetter}
        onLetterClick={setActiveLetter}
      />

      <GlossaryGrid
        terms={filteredTerms}
        categories={categories}
        selectedCategory={selectedCategory}
        onCategoryChange={setSelectedCategory}
      />
    </div>
  )
}

export default GlossaryPage
