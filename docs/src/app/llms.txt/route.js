/**
 * /llms.txt — machine-readable site index for LLMs.
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
 * Links point to the .md variant of each page so that an LLM following
 * a link receives clean markdown rather than rendered HTML.
 *
 * Sections are ordered to match the sidebar (_meta.tsx order):
 *   Primary  → docs, guides, sdk, contribute
 *   Optional → individual glossary terms, changelog entries
 *   (The glossary index page itself is in the primary "Glossary" block.)
 */

import {
  getAllPages,
  SECTION_ORDER,
  SECTION_LABELS,
  OPTIONAL_SECTIONS,
} from '../../lib/content-index.js'
import { siteConfig } from '../../lib/site-config.js'

export const dynamic = 'force-dynamic'

/** Builds a canonical URL for a given URL path. */
function pageUrl(urlPath) {
  if (!urlPath) return siteConfig.siteUrl
  return `${siteConfig.siteUrl}/${urlPath}`
}

/** Builds the .md URL for a given URL path. */
function mdUrl(urlPath) {
  if (!urlPath) return `${siteConfig.siteUrl}.md`
  return `${siteConfig.siteUrl}/${urlPath}.md`
}

export async function GET() {
  const { bySection } = getAllPages()

  const lines = []

  // -------------------------------------------------------------------------
  // Header
  // -------------------------------------------------------------------------
  lines.push(`# ${siteConfig.siteName}`)
  lines.push('')
  lines.push(`> ${siteConfig.siteDescription}`)
  lines.push('')

  // -------------------------------------------------------------------------
  // Primary sections — shown as named H2 blocks
  // -------------------------------------------------------------------------
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

  // -------------------------------------------------------------------------
  // Optional section — glossary index + individual terms + changelog
  // -------------------------------------------------------------------------
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

  // -------------------------------------------------------------------------
  // Footer links
  // -------------------------------------------------------------------------
  lines.push('## Resources')
  lines.push('')
  lines.push(`- Full content (all pages concatenated): ${pageUrl('llms-full.txt')}`)
  lines.push(`- SDK API reference: https://rhesis-sdk.readthedocs.io/en/latest/`)
  lines.push(`- GitHub: https://github.com/rhesis-ai/rhesis`)
  lines.push(`- Discord: https://discord.rhesis.ai`)
  lines.push(`- Website: https://www.rhesis.ai`)

  const content = lines.join('\n')

  return new Response(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
