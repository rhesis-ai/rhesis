import { codeToHtml } from 'shiki'
import { CopyButton } from './CopyButton'

/**
 * CodeBlock Component
 *
 * A terminal-style code block component with Shiki syntax highlighting.
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

export async function CodeBlock({
  children,
  filename = 'code.txt',
  language = 'text',
  isTerminal = false,
}) {
  let code = typeof children === 'string' ? children : String(children)

  // Fix MDX auto-dedenting (MDX removes 2 spaces from each line)
  // Add 2 spaces back to indented lines to restore proper indentation
  // This converts: 2 spaces -> 4, 6 spaces -> 8, etc.
  if (language !== 'json' && language !== 'text') {
    code = code
      .split('\n')
      .map(line => {
        const leadingSpaces = line.match(/^( *)/)[1].length
        if (leadingSpaces === 0) return line
        return '  ' + line
      })
      .join('\n')
  }

  // Format JSON automatically (uses 2-space indent)
  if (language === 'json') {
    try {
      const parsed = JSON.parse(code)
      code = JSON.stringify(parsed, null, 2)
    } catch (e) {
      // Keep original if parsing fails
    }
  }

  // Map language to Shiki language identifier
  const shikiLang = isTerminal ? 'bash' : language === 'text' ? 'plaintext' : language

  // Use Shiki for syntax highlighting
  const highlighted = await codeToHtml(code, {
    lang: shikiLang,
    theme: 'github-dark',
  })

  const styles = {
    container: {
      fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
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
    content: {
      padding: '16px',
      overflowX: 'auto',
      fontSize: '14px',
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
        <CopyButton code={code} />
      </div>
      <div style={styles.content} dangerouslySetInnerHTML={{ __html: highlighted }} />
    </div>
  )
}

export default CodeBlock
