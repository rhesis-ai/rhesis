'use client'

import React from 'react'

/**
 * Table Component
 *
 * A full-width table component that aligns with the Rhesis theme.
 * Features responsive design, theme-aware styling, and clean typography.
 *
 * Usage in MDX files:
 * ```mdx
 * import { Table } from '@/components/Table'
 *
 * <Table
 *   headers={['Service', 'Port', 'Description', 'Health Check']}
 *   rows={[
 *     ['PostgreSQL', '5432', 'Primary database', 'pg_isready'],
 *     ['Redis', '6379', 'Cache & message broker', 'redis-cli ping'],
 *   ]}
 * />
 * ```
 *
 * Or with custom alignment:
 * ```mdx
 * <Table
 *   headers={['Resource', 'Minimum', 'Recommended']}
 *   rows={[
 *     ['RAM', '4 GB', '6 GB'],
 *     ['Storage', '8 GB free', '15 GB free'],
 *   ]}
 *   align={['left', 'center', 'center']}
 * />
 * ```
 */
export const Table = ({
  headers = [],
  rows = [],
  align = [],
  caption = null,
  striped = true,
  hoverable = true,
  className = '',
}) => {
  const styles = {
    wrapper: {
      width: '100%',
      overflowX: 'auto',
      margin: '1.5rem 0',
      borderRadius: '0.75rem',
      border: '1px solid var(--table-border, #e5e7eb)',
      backgroundColor: 'var(--table-wrapper-bg, #ffffff)',
      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
    },
    table: {
      width: '100%',
      borderCollapse: 'collapse',
      fontFamily: "'Be Vietnam Pro', sans-serif",
      fontSize: '0.9375rem',
      lineHeight: '1.6',
    },
    caption: {
      padding: '0.75rem 1rem',
      textAlign: 'left',
      fontWeight: '600',
      fontSize: '1rem',
      fontFamily: "'Sora', sans-serif",
      color: 'var(--text-primary, #3d3d3d)',
      borderBottom: '1px solid var(--table-border, #e5e7eb)',
    },
    thead: {
      backgroundColor: 'var(--table-header-bg, #f9fafb)',
      borderBottom: '2px solid var(--table-border-dark, #d1d5db)',
    },
    th: {
      padding: '0.875rem 1rem',
      textAlign: 'left',
      fontWeight: '600',
      fontSize: '0.875rem',
      color: 'var(--text-primary, #3d3d3d)',
      fontFamily: "'Sora', sans-serif",
      letterSpacing: '0.025em',
      textTransform: 'uppercase',
    },
    tbody: {},
    tr: {
      borderBottom: '1px solid var(--table-border, #e5e7eb)',
      transition: 'background-color 0.15s ease',
    },
    td: {
      padding: '0.875rem 1rem',
      color: 'var(--text-primary, #3d3d3d)',
      verticalAlign: 'top',
    },
    code: {
      backgroundColor: 'var(--code-bg, #f3f4f6)',
      color: 'var(--code-text, #2aa1ce)',
      padding: '0.125rem 0.375rem',
      borderRadius: '0.25rem',
      fontSize: '0.875em',
      fontFamily: "'Fira Code', 'Monaco', 'Consolas', monospace",
    },
  }

  // Helper function to check if content looks like code
  const isCodeLike = content => {
    if (typeof content !== 'string') return false
    return (
      content.includes('`') ||
      content.includes('curl') ||
      content.includes('pg_') ||
      content.includes('redis-') ||
      content.includes('docker') ||
      content.includes('/') ||
      content.match(/^\d{4,}$/)
    ) // port numbers
  }

  // Helper function to render cell content with code formatting and bold
  const renderCellContent = content => {
    if (typeof content !== 'string') return content

    // Check if the entire content is wrapped in ** for bold
    if (content.startsWith('**') && content.endsWith('**')) {
      const boldContent = content.slice(2, -2)
      return <strong style={{ fontWeight: '600' }}>{boldContent}</strong>
    }

    // Check if the entire content should be code
    if (content.startsWith('`') && content.endsWith('`')) {
      return <code style={styles.code}>{content.slice(1, -1)}</code>
    }

    // Check if it looks like code
    if (isCodeLike(content)) {
      return <code style={styles.code}>{content}</code>
    }

    return content
  }

  // Get alignment for a column
  const getAlignment = index => {
    return align[index] || 'left'
  }

  return (
    <div style={styles.wrapper} className={`rhesis-table ${className}`}>
      <table style={styles.table}>
        {caption && <caption style={styles.caption}>{caption}</caption>}

        {headers.length > 0 && (
          <thead style={styles.thead}>
            <tr>
              {headers.map((header, index) => (
                <th
                  key={index}
                  style={{
                    ...styles.th,
                    textAlign: getAlignment(index),
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
        )}

        <tbody style={styles.tbody}>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              style={styles.tr}
              className={`
                ${striped && rowIndex % 2 === 1 ? 'table-row-striped' : ''}
                ${hoverable ? 'table-row-hoverable' : ''}
              `}
            >
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  style={{
                    ...styles.td,
                    textAlign: getAlignment(cellIndex),
                  }}
                >
                  {renderCellContent(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default Table
