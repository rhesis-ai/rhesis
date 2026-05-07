/**
 * Converts MDX source to clean markdown for LLM consumption.
 *
 * Approach: pragmatic text-based transforms rather than a full AST parse.
 * Minor residual noise is acceptable — LLMs handle it gracefully.
 *
 * Processing order matters:
 *  1. Protect fenced code blocks (don't transform their content)
 *  2. Handle CodeBlock JSX component -> fenced code block
 *  3. Strip import/export statements
 *  4. Convert known JSX components to markdown equivalents
 *  5. Strip remaining JSX tags (keep text children of block components)
 *  6. Drop leftover JSX expressions
 *  7. Restore protected code blocks
 *  8. Clean up whitespace
 */

/**
 * Extracts the value of a named attribute from a JSX attribute string.
 * Handles double-quoted strings only (the common case in Nextra MDX).
 *
 * @param {string} attrStr - The raw attribute portion of the JSX tag
 * @param {string} name - Attribute name
 * @returns {string|null}
 */
function attr(attrStr, name) {
  const m = attrStr.match(new RegExp(`\\b${name}="([^"]*)"`, 'i'))
  return m ? m[1] : null
}

/**
 * Converts MDX source to clean markdown.
 *
 * @param {string} source - Raw MDX source
 * @param {{ url?: string, title?: string }} [meta] - Optional metadata to prepend
 * @returns {string} - Clean markdown
 */
export function cleanMdxToMarkdown(source, meta = {}) {
  if (!source) return ''

  let result = source

  // -------------------------------------------------------------------------
  // Step 0: Strip existing YAML frontmatter (--- ... ---) so we can prepend
  // our own clean version at the end.
  // -------------------------------------------------------------------------
  result = result.replace(/^---\n[\s\S]*?\n---\n?/, '')

  // -------------------------------------------------------------------------
  // Step 1: Protect existing fenced code blocks from transformation.
  // -------------------------------------------------------------------------
  const codeBlocks = []
  result = result.replace(/```[\s\S]*?```/g, match => {
    const idx = codeBlocks.length
    codeBlocks.push(match)
    return `\x00CB${idx}\x00`
  })

  // -------------------------------------------------------------------------
  // Step 2: CodeBlock JSX component -> fenced code block.
  //
  // Handles the two common patterns:
  //   <CodeBlock language="bash">{`content`}</CodeBlock>
  //   <CodeBlock filename="file.py" language="python">{`content`}</CodeBlock>
  // -------------------------------------------------------------------------
  result = result.replace(/<CodeBlock\s([^>]*?)>([\s\S]*?)<\/CodeBlock>/gs, (_, attrStr, inner) => {
    const lang = attr(attrStr, 'language') || ''
    // Extract content from template literal expression {`...`}
    const tmplMatch = inner.match(/\{`([\s\S]*?)`\}/)
    const code = tmplMatch ? tmplMatch[1].trim() : inner.trim()
    if (!code) return ''
    const block = `\`\`\`${lang}\n${code}\n\`\`\``
    codeBlocks.push(block)
    return `\x00CB${codeBlocks.length - 1}\x00`
  })

  // -------------------------------------------------------------------------
  // Step 3: Remove import / export statements (at line start).
  // -------------------------------------------------------------------------
  result = result.replace(/^import\s[^\n]*\n?/gm, '')
  result = result.replace(/^export\s+default\s[^\n]*\n?/gm, '')
  result = result.replace(/^export\s+(?:const|let|var|function|async)\s[^\n]*\n?/gm, '')

  // -------------------------------------------------------------------------
  // Step 4a: Template literals remaining in JSX expressions -> content.
  // -------------------------------------------------------------------------
  result = result.replace(/\{`([\s\S]*?)`\}/g, (_, content) => content)

  // -------------------------------------------------------------------------
  // Step 4b: NextStepCard -> markdown bullet link.
  //
  // Handles multi-line self-closing tags like:
  //   <NextStepCard
  //     emoji="..."
  //     title="..."
  //     description="..."
  //     link="..."
  //   />
  // -------------------------------------------------------------------------
  result = result.replace(/<NextStepCard\s([^>]*?)\/>/gs, (_, attrStr) => {
    const title = attr(attrStr, 'title')
    const link = attr(attrStr, 'link')
    const description = attr(attrStr, 'description')
    if (!title || !link) return ''
    return `- [${title}](${link})${description ? ': ' + description : ''}`
  })

  // -------------------------------------------------------------------------
  // Step 4c: Callout -> blockquote.
  // -------------------------------------------------------------------------
  result = result.replace(/<Callout[^>]*>([\s\S]*?)<\/Callout>/gs, (_, content) => {
    const trimmed = content.trim()
    if (!trimmed) return ''
    return trimmed
      .split('\n')
      .map(line => `> ${line}`)
      .join('\n')
  })

  // -------------------------------------------------------------------------
  // Step 4d: YouTubeEmbed -> plain link.
  // -------------------------------------------------------------------------
  result = result.replace(/<YouTubeEmbed\s([^>]*?)\/>/gs, (_, attrStr) => {
    const videoId = attr(attrStr, 'videoId')
    if (!videoId) return ''
    return `[Watch on YouTube](https://www.youtube.com/watch?v=${videoId})`
  })

  // -------------------------------------------------------------------------
  // Step 4e: ThemeAwareImage -> markdown image (fall back to empty).
  // -------------------------------------------------------------------------
  result = result.replace(/<ThemeAwareImage\s([^>]*?)\/>/gs, (_, attrStr) => {
    const src = attr(attrStr, 'src') || attr(attrStr, 'lightSrc') || ''
    const alt = attr(attrStr, 'alt') || 'Image'
    return src ? `![${alt}](${src})` : ''
  })

  // -------------------------------------------------------------------------
  // Step 5a: Drop components that have no useful text content for LLMs.
  //   - Visual/decorative components
  //   - Data-driven components whose props are JS arrays (Table, FileTree)
  // -------------------------------------------------------------------------
  const DROP_COMPONENTS = [
    'NextStepCardGrid',
    'ButtonGroup',
    'CommunitySupport',
    'GitHubStarBanner',
    'CollapsibleSidebar',
    'FeatureOverview',
    'IndustryExamples',
    'DevelopmentResourcesGrid',
    'ArchitectureOverview',
    'ObservabilitySection',
    'TestsSection',
    'McpSection',
    'ModelProvidersSection',
    'Table',
    'FileTree',
  ]
  for (const comp of DROP_COMPONENTS) {
    // Block form with children
    result = result.replace(new RegExp(`<${comp}[\\s\\S]*?<\\/${comp}>`, 'gs'), '')
    // Self-closing (may span multiple lines due to props)
    result = result.replace(new RegExp(`<${comp}(\\s[^>]*)?\\/>`, 'gs'), '')
  }

  // -------------------------------------------------------------------------
  // Step 5b: Transparent wrapper components — strip tags, keep text children.
  // -------------------------------------------------------------------------
  const TRANSPARENT_COMPONENTS = [
    'Steps',
    'Step',
    'Tabs',
    'Tab',
    'Cards',
    'Card',
    'Frame',
    'Accordion',
    'AccordionItem',
  ]
  for (const comp of TRANSPARENT_COMPONENTS) {
    result = result.replace(new RegExp(`<${comp}[^>]*>([\\s\\S]*?)<\\/${comp}>`, 'gs'), '$1')
  }

  // -------------------------------------------------------------------------
  // Step 5c: HTML-style elements — convert anchors, drop the rest.
  // -------------------------------------------------------------------------
  result = result.replace(/<a\s[^>]*?href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, '[$2]($1)')
  result = result.replace(/<img\s[^>]*?alt="([^"]*)"[^>]*?\/?>/gi, '[$1]')

  // -------------------------------------------------------------------------
  // Step 5d: Strip remaining JSX/HTML tags (keep any text between them).
  //   Only strip PascalCase component tags and lowercase HTML tags that are
  //   safe to remove (not inline formatting like <strong>, <em>, <code>).
  // -------------------------------------------------------------------------
  // PascalCase components (self-closing)
  result = result.replace(/<[A-Z][A-Za-z0-9.]*(?:\s[^>]*)?\s*\/>/gs, '')
  // PascalCase components (closing tag)
  result = result.replace(/<\/[A-Z][A-Za-z0-9.]*>/g, '')
  // PascalCase components (opening tag with optional attrs)
  result = result.replace(/<[A-Z][A-Za-z0-9.]*(?:\s[^>]*)?>/gs, '')

  // Block-level HTML elements to strip (keep inline like strong/em/code)
  const BLOCK_HTML = [
    'div',
    'section',
    'article',
    'aside',
    'header',
    'footer',
    'nav',
    'main',
    'span',
    'figure',
    'figcaption',
    'details',
    'summary',
    'br',
    'hr',
  ]
  for (const tag of BLOCK_HTML) {
    result = result.replace(new RegExp(`<${tag}(?:\\s[^>]*)?\\/?>`, 'gi'), '')
    result = result.replace(new RegExp(`<\\/${tag}>`, 'gi'), '')
  }

  // -------------------------------------------------------------------------
  // Step 6: Drop remaining JSX expressions {expr}.
  //   Only strip braces whose contents look like a real JS expression
  //   (contain JS-specific syntax). Plain identifier-only braces such as
  //   `{id}` or path placeholders like `/test_results/{id}` are PRESERVED so
  //   that prose using brace notation survives intact.
  // -------------------------------------------------------------------------
  // Characters that are strong indicators of a JS expression (operators,
  // calls, member access, spread, string/template literals, comparisons).
  // Plain identifiers/words/digits/hyphens won't match.
  const JSX_EXPR_SIGNALS = /[(){}[\]=,?:&|<>+*/`'"]|\.{2,}/
  result = result.replace(/\{([^}\n]{0,200})\}/g, (match, inner) => {
    if (JSX_EXPR_SIGNALS.test(inner)) return ''
    return match
  })

  // -------------------------------------------------------------------------
  // Step 7: Restore protected code blocks.
  // -------------------------------------------------------------------------
  result = result.replace(/\x00CB(\d+)\x00/g, (_, idx) => codeBlocks[parseInt(idx, 10)])

  // -------------------------------------------------------------------------
  // Step 8: Clean up whitespace.
  // -------------------------------------------------------------------------
  result = result.replace(/[ \t]+$/gm, '') // trailing spaces
  result = result.replace(/\n{3,}/g, '\n\n') // collapse blank lines

  result = result.trim()

  // -------------------------------------------------------------------------
  // Step 9: Optional frontmatter block with URL / title.
  // -------------------------------------------------------------------------
  if (meta.url || meta.title) {
    const fmLines = ['---']
    if (meta.url) fmLines.push(`url: ${meta.url}`)
    if (meta.title) fmLines.push(`title: ${meta.title}`)
    fmLines.push('---', '')
    result = fmLines.join('\n') + result
  }

  return result
}
