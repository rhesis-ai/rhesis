import React from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import LabelIcon from '@mui/icons-material/Label'
import LinkIcon from '@mui/icons-material/Link'
import { CodeBlock } from '../CodeBlock'
import { InteractiveLink } from './InteractiveLink'
import glossaryDataRaw from '../../../content/glossary/glossary-terms.jsonl'

// Parse JSONL format (one JSON object per line)
const glossaryData = {
  terms: glossaryDataRaw
    .trim()
    .split('\n')
    .map(line => JSON.parse(line)),
}

/**
 * Simple hash function to generate stable keys from content
 */
function simpleHash(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(36)
}

/**
 * Process markdown content to extract code blocks and render them with CodeBlock
 */
async function renderMarkdownWithCodeBlocks(markdown) {
  // Split by code blocks
  const parts = []
  const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
  let lastIndex = 0
  let match

  while ((match = codeBlockRegex.exec(markdown)) !== null) {
    // Add markdown before code block
    if (match.index > lastIndex) {
      const content = markdown.slice(lastIndex, match.index)
      parts.push({
        type: 'markdown',
        content,
        key: `md-${simpleHash(content)}`,
      })
    }

    // Add code block
    const language = match[1] || 'text'
    const code = match[2]
    parts.push({
      type: 'code',
      language,
      code,
      key: `code-${language}-${simpleHash(code)}`,
    })

    lastIndex = match.index + match[0].length
  }

  // Add remaining markdown
  if (lastIndex < markdown.length) {
    const content = markdown.slice(lastIndex)
    parts.push({
      type: 'markdown',
      content,
      key: `md-${simpleHash(content)}`,
    })
  }

  return parts
}

/**
 * GlossaryTermPage Component
 *
 * Displays an individual glossary term with full details on its own page.
 * Used for SEO-optimized individual term pages.
 *
 * @param {Object} props - Component props
 * @param {string} props.termId - The ID of the term to display
 */
export const GlossaryTermPage = async ({ termId }) => {
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
    marginTop: '1.5rem',
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

  const definitionBoxStyles = {
    padding: '1.5rem',
    backgroundColor: 'rgba(14, 165, 233, 0.05)',
    border: '2px solid rgba(14, 165, 233, 0.2)',
    borderRadius: '8px',
    marginBottom: '2.5rem',
  }

  const definitionStyles = {
    fontSize: '1.1rem',
    lineHeight: '1.7',
    color: 'var(--nextra-content-color)',
    margin: 0,
    fontWeight: '400',
  }

  const extendedContentStyles = {
    fontSize: '1rem',
    lineHeight: '1.8',
    color: 'var(--nextra-content-color)',
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
      <InteractiveLink href="/glossary" style={backLinkStyles} hoverStyle={{ opacity: '0.7' }}>
        <ArrowBackIcon style={{ fontSize: '18px' }} />
        Back to Glossary
      </InteractiveLink>

      <InteractiveLink
        href={`/glossary?category=${encodeURIComponent(term.category)}`}
        style={categoryBadgeStyles}
        hoverStyle={{
          backgroundColor: '#0ea5e9',
          color: '#ffffff',
        }}
      >
        <LabelIcon style={{ fontSize: '14px' }} />
        {term.category}
      </InteractiveLink>

      <div style={definitionBoxStyles}>
        <p style={definitionStyles}>{term.definition}</p>
      </div>

      {term.aliases && term.aliases.length > 0 && (
        <div style={aliasesStyles}>Also known as: {term.aliases.join(', ')}</div>
      )}

      {term.extendedContent && (
        <div style={extendedContentStyles}>
          {await (async () => {
            const parts = await renderMarkdownWithCodeBlocks(term.extendedContent)
            return parts.map(part => {
              if (part.type === 'code') {
                return (
                  <CodeBlock key={part.key} language={part.language} filename={part.language}>
                    {part.code}
                  </CodeBlock>
                )
              }
              return (
                <ReactMarkdown
                  key={part.key}
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h2: ({ node, ...props }) => (
                      <h2
                        style={{
                          fontSize: '1.5rem',
                          fontWeight: '600',
                          marginTop: '2rem',
                          marginBottom: '1rem',
                          color: 'var(--nextra-content-color)',
                        }}
                        {...props}
                      />
                    ),
                    h3: ({ node, ...props }) => (
                      <h3
                        style={{
                          fontSize: '1.25rem',
                          fontWeight: '600',
                          marginTop: '1.5rem',
                          marginBottom: '0.75rem',
                          color: 'var(--nextra-content-color)',
                        }}
                        {...props}
                      />
                    ),
                    p: ({ node, ...props }) => (
                      <p
                        style={{
                          marginBottom: '1rem',
                          lineHeight: '1.8',
                        }}
                        {...props}
                      />
                    ),
                    ul: ({ node, ...props }) => (
                      <ul
                        style={{
                          marginBottom: '1rem',
                          paddingLeft: '1.5rem',
                          listStyleType: 'disc',
                        }}
                        {...props}
                      />
                    ),
                    ol: ({ node, ...props }) => (
                      <ol
                        style={{
                          marginBottom: '1rem',
                          paddingLeft: '1.5rem',
                        }}
                        {...props}
                      />
                    ),
                    li: ({ node, ...props }) => (
                      <li
                        style={{
                          marginBottom: '0.5rem',
                        }}
                        {...props}
                      />
                    ),
                    code: ({ node, inline, className, children, ...props }) => {
                      // Only inline code here, block code is handled separately
                      if (inline) {
                        return (
                          <code
                            style={{
                              backgroundColor: 'rgba(14, 165, 233, 0.1)',
                              padding: '0.2rem 0.4rem',
                              borderRadius: '4px',
                              fontSize: '0.9em',
                              fontFamily: 'monospace',
                            }}
                            {...props}
                          >
                            {children}
                          </code>
                        )
                      }
                      return null // Block code blocks are extracted and rendered separately
                    },
                    pre: () => null, // Pre blocks are extracted and rendered separately
                    table: ({ node, ...props }) => (
                      <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                        <table
                          style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: '0.95rem',
                          }}
                          {...props}
                        />
                      </div>
                    ),
                    th: ({ node, ...props }) => (
                      <th
                        style={{
                          border: '1px solid var(--nextra-border)',
                          padding: '0.75rem',
                          backgroundColor: 'rgba(14, 165, 233, 0.05)',
                          textAlign: 'left',
                          fontWeight: '600',
                        }}
                        {...props}
                      />
                    ),
                    td: ({ node, ...props }) => (
                      <td
                        style={{
                          border: '1px solid var(--nextra-border)',
                          padding: '0.75rem',
                        }}
                        {...props}
                      />
                    ),
                    blockquote: ({ node, ...props }) => (
                      <blockquote
                        style={{
                          borderLeft: '4px solid #0ea5e9',
                          paddingLeft: '1rem',
                          marginLeft: 0,
                          marginBottom: '1rem',
                          fontStyle: 'italic',
                          color: 'var(--nextra-content-secondary)',
                        }}
                        {...props}
                      />
                    ),
                  }}
                >
                  {part.content}
                </ReactMarkdown>
              )
            })
          })()}
        </div>
      )}

      {term.docLinks && term.docLinks.length > 0 && (
        <div>
          <h2 style={sectionTitleStyles}>
            <LinkIcon style={{ fontSize: '20px' }} />
            Documentation
          </h2>
          <div style={linkListStyles}>
            {term.docLinks.map(link => (
              <InteractiveLink
                key={link}
                href={link}
                style={docLinkStyles}
                hoverStyle={{ opacity: '0.7' }}
              >
                <LinkIcon style={{ fontSize: '16px' }} />
                {link}
              </InteractiveLink>
            ))}
          </div>
        </div>
      )}

      {term.relatedTerms && term.relatedTerms.length > 0 && (
        <div>
          <h2 style={sectionTitleStyles}>Related Terms</h2>
          <div style={relatedTermsGridStyles}>
            {term.relatedTerms.map(relatedId => (
              <InteractiveLink
                key={relatedId}
                href={`/glossary/${relatedId}`}
                style={relatedTermLinkStyles}
                hoverStyle={{
                  backgroundColor: '#0ea5e9',
                  color: '#ffffff',
                  transform: 'translateY(-2px)',
                }}
              >
                {getTermNameById(relatedId)}
              </InteractiveLink>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default GlossaryTermPage
