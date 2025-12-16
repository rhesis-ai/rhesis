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
  const [isHovering, setIsHovering] = useState(false)

  const handleCopy = async () => {
    const code = typeof children === 'string' ? children : String(children)
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      // Silently fail - clipboard copy is not critical functionality
    }
  }

  // Fix MDX auto-dedenting for Python code
  // MDX automatically dedents template literals by removing 2 spaces from each line
  // This function adds back those 2 spaces to restore proper Python indentation
  const fixPythonIndentation = code => {
    if (language !== 'python') return code

    return code
      .split('\n')
      .map(line => {
        // Count leading spaces
        const leadingSpaces = line.match(/^( *)/)[1].length
        if (leadingSpaces === 0) return line

        // Add 2 spaces to every indented line to compensate for MDX dedenting
        // This converts: 2 spaces -> 4, 6 spaces -> 8, 10 spaces -> 12, etc.
        return '  ' + line
      })
      .join('\n')
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
      // Apply highlighting in order: comments first (to catch entire commented lines), then strings, numbers, keywords
      // Each step must avoid already-highlighted content

      // 1. Comments first - treat entire lines starting with # as comments (even if they contain code-like structures)
      highlightedCode = highlightedCode
        .split('\n')
        .map(line => {
          // If line starts with # (optionally preceded by whitespace), treat entire line as comment
          if (/^\s*#/.test(line)) {
            return '<span class="code-comment">' + line + '</span>'
          }
          return line
        })
        .join('\n')

      // 2. Strings (to protect content inside strings) - avoid already commented lines
      // Handle triple-quoted strings first (they can contain quotes inside)
      let parts = highlightedCode.split(/(<span class="code-comment">.*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          if (part.includes('class="code-comment"')) {
            return part
          }
          return part
            .replace(/"""[\s\S]*?"""/g, '<span class="code-string">$&</span>')
            .replace(/'''[\s\S]*?'''/g, '<span class="code-string">$&</span>')
        })
        .join('')

      // Then handle single-line strings (avoid already-highlighted content)
      const stringParts = highlightedCode.split(/(<span class="code-[^"]*">[\s\S]*?<\/span>)/g)
      highlightedCode = stringParts
        .map(part => {
          if (part.includes('class="code-')) {
            return part
          }
          // Apply single-line string highlighting
          return part
            .replace(/"(?:[^"\\\n]|\\.)*"/g, '<span class="code-string">$&</span>')
            .replace(/'(?:[^'\\\n]|\\.)*'/g, '<span class="code-string">$&</span>')
        })
        .join('')

      // 3. Inline comments (# and everything after) - avoid matching inside strings and already commented lines
      let commentParts = highlightedCode.split(/(<span class="code-[^"]*">[\s\S]*?<\/span>)/g)
      highlightedCode = commentParts
        .map(part => {
          if (part.includes('class="code-')) {
            return part
          }
          return part.replace(/#.*$/, '<span class="code-comment">$&</span>')
        })
        .join('')

      // 4. Numbers - avoid inside strings and comments
      let numberParts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = numberParts
        .map(part => {
          if (part.startsWith('<span')) {
            return part
          }
          return part.replace(/\b\d+\.?\d*\b/g, '<span class="code-number">$&</span>')
        })
        .join('')

      // 5. Keywords - avoid inside strings, comments, and numbers
      let keywordParts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = keywordParts
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
        /"(?:[^"\\\n]|\\.)*"/g,
        '<span class="code-string">$&</span>'
      )
      highlightedCode = highlightedCode.replace(
        /'(?:[^'\\\n]|\\.)*'/g,
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
      const commandParts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = commandParts
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
      // Apply highlighting in order: strings, comments, numbers, keywords (true/false/null)

      // 1. Strings first (including keys and values)
      highlightedCode = highlightedCode.replace(
        /"(?:[^"\\\n]|\\.)*"/g,
        '<span class="code-string">$&</span>'
      )

      // 2. Comments - treat entire lines starting with # as comments (even if they contain JSON-like structures)
      highlightedCode = highlightedCode
        .split('\n')
        .map(line => {
          // If line starts with # (optionally preceded by whitespace), treat entire line as comment
          if (/^\s*#/.test(line)) {
            return '<span class="code-comment">' + line + '</span>'
          }
          
          // For other lines, only highlight # and everything after it as comments, avoiding strings
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
      let jsonNumberParts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = jsonNumberParts
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

      // 4. Keywords (true, false, null) - avoid inside strings, comments, and numbers
      let jsonKeywordParts = highlightedCode.split(/(<span[^>]*>[\s\S]*?<\/span>)/g)
      highlightedCode = jsonKeywordParts
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

  // Fix Python indentation (MDX dedents template literals, converting 4 spaces to 2)
  code = fixPythonIndentation(code)

  // Auto-format JSON if language is json
  if (language === 'json') {
    code = formatJSON(code)
  }

  const processedCode = applySyntaxHighlighting(code)

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
