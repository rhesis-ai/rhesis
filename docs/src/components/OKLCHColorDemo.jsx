'use client'

import { CATEGORICAL_COLORS, getCategoricalVar } from '@/utils/oklch-colors'

/**
 * Demo component showing OKLCH categorical colors
 * Colors remain identical across light and dark themes
 */
export function OKLCHColorDemo() {
  const colors = Object.entries(CATEGORICAL_COLORS)

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '1rem',
        padding: '1rem',
        marginTop: '1rem',
        marginBottom: '1rem',
      }}
    >
      {colors.map(([name, color], index) => (
        <div
          key={name}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <div
            style={{
              width: '80px',
              height: '80px',
              backgroundColor: getCategoricalVar(index + 1),
              borderRadius: '8px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              border: '2px solid var(--mermaid-line)',
            }}
          />
          <div
            style={{
              fontSize: '0.75rem',
              fontWeight: '500',
              color: 'var(--mermaid-text)',
              textAlign: 'center',
            }}
          >
            {name}
          </div>
          <code
            style={{
              fontSize: '0.625rem',
              color: 'var(--mermaid-text)',
              opacity: 0.7,
              textAlign: 'center',
              wordBreak: 'break-all',
            }}
          >
            {color}
          </code>
        </div>
      ))}
    </div>
  )
}

/**
 * Inline color swatch component
 */
export function ColorSwatch({ index, size = 16 }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: `${size}px`,
        height: `${size}px`,
        backgroundColor: getCategoricalVar(index),
        borderRadius: '3px',
        border: '1px solid var(--mermaid-line)',
        verticalAlign: 'middle',
        marginLeft: '4px',
        marginRight: '4px',
      }}
    />
  )
}
