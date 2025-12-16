'use client'

import { useState, useEffect } from 'react'

export default function GitHubStarBanner() {
  const [isVisible, setIsVisible] = useState(false)
  const storageKey = 'star-banner-2025-dismissed'

  useEffect(() => {
    // Check if banner was previously dismissed
    const isDismissed = localStorage.getItem(storageKey) === 'true'
    setIsVisible(!isDismissed)
  }, [])

  const handleDismiss = () => {
    setIsVisible(false)
    localStorage.setItem(storageKey, 'true')
  }

  if (!isVisible) {
    return null
  }

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #2aa1ce 0%, #3bc4f2 100%)',
        padding: '5px 16px',
        minHeight: '32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        fontFamily: 'Be Vietnam Pro, sans-serif',
      }}
    >
      <a
        href="https://github.com/rhesis-ai/rhesis"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.5rem',
          textDecoration: 'none',
          color: '#ffffff',
          fontWeight: 500,
          fontSize: '14px',
          transition: 'opacity 0.2s ease-in-out',
        }}
        onMouseEnter={e => (e.target.style.opacity = '0.9')}
        onMouseLeave={e => (e.target.style.opacity = '1')}
      >
        ⭐ If you find Rhesis useful, please star us on GitHub! →
      </a>

      <button
        onClick={handleDismiss}
        style={{
          position: 'absolute',
          right: '12px',
          background: 'transparent',
          border: 'none',
          color: '#ffffff',
          opacity: 0.8,
          cursor: 'pointer',
          padding: '2px',
          borderRadius: '3px',
          width: '20px',
          height: '20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease-in-out',
        }}
        onMouseEnter={e => {
          e.target.style.opacity = '1'
          e.target.style.background = 'rgba(255, 255, 255, 0.1)'
        }}
        onMouseLeave={e => {
          e.target.style.opacity = '0.8'
          e.target.style.background = 'transparent'
        }}
        aria-label="Dismiss banner"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  )
}
