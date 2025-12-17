'use client'

import { useState } from 'react'

export function CopyButton({ code }) {
  const [copied, setCopied] = useState(false)
  const [isHovering, setIsHovering] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      // Silently fail - clipboard copy is not critical functionality
    }
  }

  const styles = {
    copyButton: {
      background: 'transparent',
      border: '1px solid #30363D',
      borderRadius: '4px',
      padding: '4px 8px',
      color: '#A9B1BB',
      cursor: 'pointer',
      fontSize: '11px',
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      transition: 'all 0.2s ease',
    },
    copyButtonHover: {
      background: '#30363D',
      color: '#E6EDF3',
    },
    copyButtonCopied: {
      background: '#238636',
      borderColor: '#238636',
      color: '#FFFFFF',
    },
  }

  return (
    <button
      onClick={handleCopy}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      style={{
        ...styles.copyButton,
        ...(copied ? styles.copyButtonCopied : isHovering ? styles.copyButtonHover : {}),
      }}
      aria-label="Copy code to clipboard"
    >
      {copied ? (
        <>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path
              d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"
              fill="currentColor"
            />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path
              d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"
              fill="currentColor"
            />
            <path
              d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"
              fill="currentColor"
            />
          </svg>
          Copy
        </>
      )}
    </button>
  )
}
