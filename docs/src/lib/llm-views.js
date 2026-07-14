/**
 * Renderers for the LLM-ingestion views:
 *   - /llms.txt           (curated index, llmstxt.org spec)
 *   - /llms-full.txt      (full corpus, all pages concatenated)
 *   - /<page>.md          (single page as clean markdown)
 *
 * The route handlers in app/ are thin Response wrappers around these
 * functions. Keeping the logic in lib/ means it is unit-testable without
 * having to load Next.js runtime modules.
 */

import fs from 'fs'

import {
  findContentDir,
  getAllPagesCached,
  urlToFilePath,
  SECTION_ORDER,
  SECTION_LABELS,
  OPTIONAL_SECTIONS,
} from './content-index.js'
import { cleanMdxToMarkdown } from './mdx-to-markdown.js'
import { siteConfig } from './site-config.js'

// ---------------------------------------------------------------------------
// Internal URL helpers
// ---------------------------------------------------------------------------

function pageUrl(urlPath) {
  if (!urlPath) return siteConfig.siteUrl
  return `${siteConfig.siteUrl}/${urlPath}`
}

function mdUrl(urlPath) {
  if (!urlPath) return `${siteConfig.siteUrl}.md`
  return `${siteConfig.siteUrl}/${urlPath}.md`
}

// ---------------------------------------------------------------------------
// /llms.txt
// ---------------------------------------------------------------------------

/**
 * Renders the /llms.txt body.
 *
 * Format follows https://llmstxt.org/:
 *   # Site Name
 *   > One-line description
 *
 *   ## Section
 *   - [Page Title](url.md): Short description.
 *
 *   ## Optional
 *   - [Page Title](url.md)
 *
 * @returns {string}
 */
export function renderLlmsTxt() {
  const { bySection } = getAllPagesCached()
  const lines = []

  // Header
  lines.push(`# ${siteConfig.siteName}`)
  lines.push('')
  lines.push(`> ${siteConfig.siteDescription}`)
  lines.push('')

  // Agent ingestion — how machines should use this index
  lines.push('## For AI agents')
  lines.push('')
  lines.push('> Read this section first if you are an LLM agent (Cursor, Claude Code, Telemachus, MCP).')
  lines.push('> Fetch linked `.md` URLs — do not scrape HTML. One concept per fetch; do not load llms-full.txt unless you need the full corpus.')
  lines.push('')
  lines.push('- [For AI agents](https://docs.rhesis.ai/docs/agent-skill/for-agents.md): routing table and reading rules')
  lines.push('- [Platform definitions](https://docs.rhesis.ai/docs/agent-skill/definitions.md): behaviors, metrics, test sets, terms')
  lines.push('- [Metric scope](https://docs.rhesis.ai/docs/metrics/metric-scope.md): Single-Turn vs Multi-Turn alignment (critical)')
  lines.push('- [PRD workflow](https://docs.rhesis.ai/docs/agent-skill/prd.md): requirements → test foundation')
  lines.push('- [Architect workflow](https://docs.rhesis.ai/docs/architect/workflow.md): native UI agent phases')
  lines.push('- [Agent skill install](https://docs.rhesis.ai/docs/agent-skill/platform.md): MCP + `npx skills add`')
  lines.push('- Golden PRD example (repo only): https://github.com/rhesis-ai/rhesis/blob/main/skills/rhesis/references/use-case-bracketfeld.md')
  lines.push('')

  // Primary sections — shown as named H2 blocks
  const primarySections = SECTION_ORDER.filter(sec => !OPTIONAL_SECTIONS.has(sec))
  for (const sec of primarySections) {
    const pages = bySection[sec] || []
    if (pages.length === 0) continue

    lines.push(`## ${SECTION_LABELS[sec]}`)
    lines.push('')
    for (const page of pages) {
      const url = mdUrl(page.urlPath)
      const desc = page.description ? `: ${page.description}` : ''
      lines.push(`- [${page.title}](${url})${desc}`)
    }
    lines.push('')
  }

  // Optional section — glossary terms + changelog
  const optionalLines = []
  for (const sec of SECTION_ORDER.filter(sec => OPTIONAL_SECTIONS.has(sec))) {
    const pages = bySection[sec] || []
    if (pages.length === 0) continue

    optionalLines.push(`### ${SECTION_LABELS[sec]}`)
    optionalLines.push('')
    for (const page of pages) {
      const url = mdUrl(page.urlPath)
      const desc = page.description ? `: ${page.description}` : ''
      optionalLines.push(`- [${page.title}](${url})${desc}`)
    }
    optionalLines.push('')
  }
  if (optionalLines.length > 0) {
    lines.push('## Optional')
    lines.push('')
    lines.push(...optionalLines)
  }

  // Footer / resources
  lines.push('## Resources')
  lines.push('')
  lines.push(`- Full content (all pages concatenated): ${pageUrl('llms-full.txt')}`)
  lines.push(`- SDK API reference: https://rhesis-sdk.readthedocs.io/en/latest/`)
  lines.push(`- GitHub: https://github.com/rhesis-ai/rhesis`)
  lines.push(`- Discord: https://discord.rhesis.ai`)
  lines.push(`- Website: https://www.rhesis.ai`)

  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// /llms-full.txt
// ---------------------------------------------------------------------------

/**
 * Renders the /llms-full.txt body.
 *
 * Concatenates every page's cleaned markdown. The per-page YAML frontmatter
 * (emitted by cleanMdxToMarkdown) doubles as the page boundary, so we don't
 * need any additional separator between pages.
 *
 * @returns {string}
 */
export function renderLlmsFullTxt() {
  const { bySection } = getAllPagesCached()
  const chunks = []

  chunks.push(`# ${siteConfig.siteName} (full)`)
  chunks.push('')
  chunks.push(`> ${siteConfig.siteDescription}`)
  chunks.push('')
  chunks.push(`> This file contains the complete documentation corpus for LLM ingestion.`)
  chunks.push(`> For a curated index with links, see ${siteConfig.siteUrl}/llms.txt`)
  chunks.push('')

  for (const sec of SECTION_ORDER) {
    const pages = bySection[sec] || []
    for (const page of pages) {
      // Skip synthesized pages that have no source (e.g. un-generated glossary terms)
      if (!page.rawSource) continue

      const canonicalUrl = page.urlPath
        ? `${siteConfig.siteUrl}/${page.urlPath}`
        : siteConfig.siteUrl

      const cleaned = cleanMdxToMarkdown(page.rawSource, {
        url: canonicalUrl,
        title: page.title,
      })
      if (!cleaned) continue

      chunks.push(cleaned)
      chunks.push('')
    }
  }

  return chunks.join('\n')
}

// ---------------------------------------------------------------------------
// /<page>.md
// ---------------------------------------------------------------------------

/**
 * Renders a single page as clean markdown.
 *
 * @param {string} urlPath - URL path without leading slash, e.g. "docs/concepts"
 * @returns {{ status: 200, body: string } | { status: 404 } | { status: 503 }}
 */
export function renderPageMarkdown(urlPath) {
  const contentDir = findContentDir()
  if (!contentDir) return { status: 503 }

  const filePath = urlToFilePath(urlPath, contentDir)
  if (!filePath) return { status: 404 }

  let rawSource
  try {
    rawSource = fs.readFileSync(filePath, 'utf8')
  } catch {
    return { status: 404 }
  }

  const canonicalUrl = urlPath ? `${siteConfig.siteUrl}/${urlPath}` : siteConfig.siteUrl

  // Title: first H1 in source, falling back to slug tail
  const h1Match = rawSource.match(/^#\s+(.+)$/m)
  const title = h1Match ? h1Match[1].trim() : (urlPath || '').split('/').pop() || 'Home'

  const body = cleanMdxToMarkdown(rawSource, { url: canonicalUrl, title })
  return { status: 200, body }
}
