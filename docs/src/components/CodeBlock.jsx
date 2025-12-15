'use client'

import React, { useState } from 'react'

/**
 * CodeBlock Component
 *
 * A terminal-style code block component that mimics the styling from the Rhesis website.
 * Supports both code files and terminal output with syntax highlighting colors.
 * Includes a copy-to-clipboard button for easy code copying.
 *
 * Usage in MDX files:
 * ```mdx
 * import { CodeBlock } from '@/components/CodeBlock'
 *
 * <CodeBlock
 *   filename="app.py"
 *   language="python"
 * >
 * {`import os
 * from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer
 *
 * # Set the environment variables
 * os.environ["RHESIS_BASE_URL"] = "https://api.rhesis.ai"`}
 * </CodeBlock>
 *
 * <CodeBlock
 *   filename="Terminal Output"
 *   isTerminal={true}
 * >
 * {`----------------------------------------
 * Prompt: Schedule an appointment for me next week with Dr. Smith.
 * Behavior: Reliability`}
 * </CodeBlock>
 * ```
 */

export const CodeBlock = ({
  children,
  filename = 'code.txt',
  language = 'text',
  isTerminal = false,
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const code = typeof children === 'string' ? children : String(children)
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy code:', err)
    }
  }
  // Format JSON automatically
  const formatJSON = code => {
    try {
      // Try to parse and re-format the JSON
      const parsed = JSON.parse(code)
      return JSON.stringify(parsed, null, 2)
    } catch (e) {
      // If parsing fails, return original (might already be formatted or invalid)
      return code
    }
  }

  // Apply syntax highlighting based on language
  const applySyntaxHighlighting = code => {
    if (isTerminal) {
      // For terminal output, apply subtle styling for better readability
      let terminalCode = code

      // Highlight separators/dividers
      terminalCode = terminalCode.replace(
        /^-{20,}$/gm,
        '<span class="terminal-separator">$&</span>'
      )

      // Highlight comments (lines starting with #)
      terminalCode = terminalCode.replace(/^#.*$/gm, '<span class="code-comment">$&</span>')

      // Highlight labels and values in one pass to avoid conflicts
      terminalCode = terminalCode.replace(
        /^([A-Za-z][A-Za-z\s]*?):\s*(.+)$/gm,
        '<span class="terminal-label">$1:</span> <span class="terminal-value">$2</span>'
      )

      // Highlight common bash commands (only at the beginning of lines or after whitespace)
      terminalCode = terminalCode.replace(
        /^(\s*)(cd|ls|mkdir|rm|cp|mv|git|npm|pip|docker|curl|wget|grep|find|cat|echo|export|source|uv|\.\/rh)(\s|$)/gm,
        '$1<span class="code-keyword">$2</span>$3'
      )

      return terminalCode
    }

    if (language === 'text') {
      return code
    }

    let highlightedCode = code

    if (language === 'python') {
      // Apply highlighting in order: strings, comments, numbers, keywords
      // Each step must avoid already-highlighted content

      // 1. Strings first (to protect content inside strings)
      // Handle triple-quoted strings first (they can contain quotes inside)
      highlightedCode = highlightedCode.replace(
        /"""[\s\S]*?"""/g,
        '<span class="code-string">$&</span>'
      )
      highlightedCode = highlightedCode.replace(
        /'''[\s\S]*?'''/g,
        '<span class="code-string">$&</span>'
      )
      // Then handle single-line strings (avoid already-highlighted triple-quoted strings)
      const stringParts = highlightedCode.split(/(<span class="code-string">[\s\S]*?<\/span>)/g)
      highlightedCode = stringParts
        .map(part => {
          if (part.includes('class="code-string"')) {
            return part
          }
          // Apply single-line string highlighting
          return part
            .replace(/"([^"\\]|\\.)*"/g, '<span class="code-string">$&</span>')
            .replace(/'([^'\\]|\\.)*'/g, '<span class="code-string">$&</span>')
        })
        .join('')

      // 2. Comments - avoid matching inside strings
      highlightedCode = highlightedCode
        .split('\n')
        .map(line => {
          if (line.includes('class="code-string"')) {
            const parts = line.split(/(<span class="code-string">.*?<\/span>)/)
            return parts
              .map(part => {
                if (part.includes('class="code-string"')) {
                  return part
                }
                return part.replace(/#.*$/, '<span class="code-comment">$&</span>')
              })
              .join('')
          }
          return line.replace(/#.*$/, '<span class="code-comment">$&</span>')
        })
        .join('\n')

      // 3. Numbers - avoid inside strings and comments
      let parts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          if (part.startsWith('<span')) {
            return part
          }
          return part.replace(/\b\d+\.?\d*\b/g, '<span class="code-number">$&</span>')
        })
        .join('')

      // 4. Keywords - avoid inside strings, comments, and numbers
      parts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          if (part.startsWith('<span')) {
            return part
          }
          return part.replace(
            /\b(import|from|def|class|if|else|elif|for|while|try|except|finally|with|as|return|yield|break|continue|pass|lambda|global|nonlocal|assert|del|raise|and|or|not|in|is|True|False|None)\b/g,
            '<span class="code-keyword">$1</span>'
          )
        })
        .join('')
    } else if (language === 'bash' || language === 'shell') {
      // Apply highlighting in order: strings, comments, commands
      // Each step must avoid already-highlighted content

      // 1. Strings first
      highlightedCode = highlightedCode.replace(
        /"([^"\\]|\\.)*"/g,
        '<span class="code-string">$&</span>'
      )
      highlightedCode = highlightedCode.replace(
        /'([^'\\]|\\.)*'/g,
        '<span class="code-string">$&</span>'
      )

      // 2. Comments - avoid matching inside strings
      highlightedCode = highlightedCode
        .split('\n')
        .map(line => {
          if (line.includes('class="code-string"')) {
            const parts = line.split(/(<span class="code-string">.*?<\/span>)/)
            return parts
              .map(part => {
                if (part.includes('class="code-string"')) {
                  return part
                }
                return part.replace(/#.*$/, '<span class="code-comment">$&</span>')
              })
              .join('')
          }
          return line.replace(/#.*$/, '<span class="code-comment">$&</span>')
        })
        .join('\n')

      // 3. Commands - avoid inside strings and comments
      const parts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          if (part.startsWith('<span')) {
            return part
          }
          return part.replace(
            /\b(cd|ls|mkdir|rm|cp|mv|git|npm|pip|docker|curl|wget|grep|find|cat|echo|export|source)\b/g,
            '<span class="code-keyword">$1</span>'
          )
        })
        .join('')
    } else if (language === 'json') {
      // JSON syntax highlighting
      // Apply highlighting in order: strings, numbers, keywords (true/false/null)

      // 1. Strings first (including keys and values)
      highlightedCode = highlightedCode.replace(
        /"([^"\\]|\\.)*"/g,
        '<span class="code-string">$&</span>'
      )

      // 2. Numbers - avoid inside strings
      let parts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          if (part.startsWith('<span')) {
            return part
          }
          return part.replace(
            /\b-?\d+\.?\d*([eE][+-]?\d+)?\b/g,
            '<span class="code-number">$&</span>'
          )
        })
        .join('')

      // 3. Keywords (true, false, null) - avoid inside strings and numbers
      parts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          if (part.startsWith('<span')) {
            return part
          }
          return part.replace(/\b(true|false|null)\b/g, '<span class="code-keyword">$1</span>')
        })
        .join('')
    }

    return highlightedCode
  }

  let code = typeof children === 'string' ? children : String(children)

  // Auto-format JSON if language is json
  if (language === 'json') {
    code = formatJSON(code)
  }

  const highlightedCode = applySyntaxHighlighting(code)

  const styles = {
    container: {
      fontFamily: "'Fira Code', 'Monaco', 'Consolas', monospace",
      background: '#161B22',
      borderRadius: '8px',
      margin: '24px 0',
      overflow: 'hidden',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4), 0 2px 6px rgba(0, 0, 0, 0.25)',
      border: isTerminal ? '1px solid #2C2C2C' : 'none',
    },
    header: {
      background: '#1F242B',
      padding: '8px 16px',
      fontSize: '12px',
      color: '#A9B1BB',
      borderBottom: '1px solid #2C2C2C',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    },
    headerLeft: {
      display: 'flex',
      alignItems: 'center',
    },
    dots: {
      display: 'flex',
      gap: '6px',
      marginRight: '12px',
    },
    dot: {
      width: '12px',
      height: '12px',
      borderRadius: '50%',
    },
    redDot: {
      background: '#e53935',
    },
    yellowDot: {
      background: '#fbc02d',
    },
    blueDot: {
      background: '#4cafef',
    },
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
    content: {
      padding: '16px',
      overflowX: 'auto',
      fontSize: '14px',
    },
    pre: {
      margin: '0',
      color: '#E6EDF3',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    },
  }

  const processedCode = applySyntaxHighlighting(children?.toString() || '')
  const [isHovering, setIsHovering] = useState(false)

  return (
    <div style={styles.container} className="not-prose rhesis-codeblock">
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.dots}>
            <div style={{ ...styles.dot, ...styles.redDot }}></div>
            <div style={{ ...styles.dot, ...styles.yellowDot }}></div>
            <div style={{ ...styles.dot, ...styles.blueDot }}></div>
          </div>
          <span>{filename}</span>
        </div>
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
              <svg
                width="12"
                height="12"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"
                  fill="currentColor"
                />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg
                width="12"
                height="12"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
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
      </div>
      <div style={styles.content}>
        <pre style={styles.pre}>
          <code dangerouslySetInnerHTML={{ __html: processedCode }} />
        </pre>
      </div>
    </div>
  )
}

export default CodeBlock
