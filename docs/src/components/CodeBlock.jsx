'use client'

import React from 'react'

/**
 * CodeBlock Component
 *
 * A terminal-style code block component that mimics the styling from the Rhesis website.
 * Supports both code files and terminal output with syntax highlighting colors.
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
      // Apply highlighting in order to avoid conflicts

      // 1. Strings first (to protect content inside strings)
      highlightedCode = highlightedCode.replace(
        /"([^"\\]|\\.)*"/g,
        '<span class="code-string">$&</span>'
      )
      highlightedCode = highlightedCode.replace(
        /'([^'\\]|\\.)*'/g,
        '<span class="code-string">$&</span>'
      )

      // 2. Numbers (but not hex colors like #3BC4F2)
      highlightedCode = highlightedCode.replace(
        /\b\d+\.?\d*\b/g,
        '<span class="code-number">$&</span>'
      )

      // 3. Comments - match # at start of line or after whitespace, not inside strings
      // Since strings are already wrapped, we avoid them with a more sophisticated check
      highlightedCode = highlightedCode
        .split('\n')
        .map(line => {
          // Skip if line already contains code-string span (means # is in a string)
          if (line.includes('class="code-string"')) {
            // Only highlight # if it's NOT inside the string span
            const parts = line.split(/(<span class="code-string">.*?<\/span>)/)
            return parts
              .map(part => {
                if (part.includes('class="code-string"')) {
                  return part // Keep strings as-is
                }
                // Apply comment highlighting to non-string parts
                return part.replace(/#.*$/, '<span class="code-comment">$&</span>')
              })
              .join('')
          }
          // No strings in this line, safe to highlight comments
          return line.replace(/#.*$/, '<span class="code-comment">$&</span>')
        })
        .join('\n')

      // 4. Keywords (avoid replacing if already in a span or inside HTML tags)
      // Split by span tags to avoid replacing keywords inside spans
      const parts = highlightedCode.split(/(<span[^>]*>.*?<\/span>)/g)
      highlightedCode = parts
        .map(part => {
          // Don't process parts that are already wrapped in spans
          if (part.startsWith('<span')) {
            return part
          }
          // Apply keyword highlighting to non-span parts
          return part.replace(
            /\b(import|from|def|class|if|else|elif|for|while|try|except|finally|with|as|return|yield|break|continue|pass|lambda|global|nonlocal|assert|del|raise|and|or|not|in|is|True|False|None)\b/g,
            '<span class="code-keyword">$1</span>'
          )
        })
        .join('')
    } else if (language === 'bash' || language === 'shell') {
      // 1. Strings first
      highlightedCode = highlightedCode.replace(
        /"([^"\\]|\\.)*"/g,
        '<span class="code-string">$&</span>'
      )
      highlightedCode = highlightedCode.replace(
        /'([^'\\]|\\.)*'/g,
        '<span class="code-string">$&</span>'
      )

      // 2. Comments - avoid matching # inside strings
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

      // 3. Commands (avoid replacing if already in a span)
      const parts = highlightedCode.split(/(<span[^>]*>.*?<\/span>)/g)
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
    }

    return highlightedCode
  }

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

  return (
    <div style={styles.container} className="not-prose rhesis-codeblock">
      <div style={styles.header}>
        <div style={styles.dots}>
          <div style={{ ...styles.dot, ...styles.redDot }}></div>
          <div style={{ ...styles.dot, ...styles.yellowDot }}></div>
          <div style={{ ...styles.dot, ...styles.blueDot }}></div>
        </div>
        <span>{filename}</span>
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
