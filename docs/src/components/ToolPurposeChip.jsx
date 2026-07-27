'use client'

import React from 'react'

/**
 * ToolPurposeChip Component
 *
 * A small inline badge clarifying what a tool connection is used for in
 * Rhesis (e.g. knowledge export vs. issue creation).
 *
 * Usage:
 * ```jsx
 * <ToolPurposeChip text="Knowledge export" />
 * ```
 */
export const ToolPurposeChip = ({ text }) => {
  const styles = {
    chip: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.35rem',
      padding: '0.2rem 0.65rem',
      borderRadius: '999px',
      fontSize: '0.75rem',
      fontWeight: 500,
      backgroundColor: 'var(--tool-purpose-chip-bg, #f2f9fd)',
      color: 'var(--tool-purpose-chip-color, #1c6f96)',
      border: '1px solid var(--tool-purpose-chip-border, #cfe9f5)',
      margin: '0.5rem 0 1rem 0',
    },
    label: {
      fontWeight: 700,
    },
  }

  return (
    <>
      <span style={styles.chip} className="tool-purpose-chip-rhesis">
        <span style={styles.label}>What&apos;s this for:</span> {text}
      </span>

      <style jsx>{`
        [data-theme='dark'] .tool-purpose-chip-rhesis {
          --tool-purpose-chip-bg: #132530;
          --tool-purpose-chip-color: #7fd0f5;
          --tool-purpose-chip-border: #1f4a5e;
        }

        [data-theme='light'] .tool-purpose-chip-rhesis {
          --tool-purpose-chip-bg: #f2f9fd;
          --tool-purpose-chip-color: #1c6f96;
          --tool-purpose-chip-border: #cfe9f5;
        }
      `}</style>
    </>
  )
}

export default ToolPurposeChip
