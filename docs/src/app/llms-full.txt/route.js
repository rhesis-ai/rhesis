/**
 * /llms-full.txt — full documentation corpus for LLM ingestion.
 *
 * Concatenates every page's cleaned markdown. Each page's per-page YAML
 * frontmatter (emitted by cleanMdxToMarkdown) doubles as the page boundary —
 * an extra "---" separator between pages would produce ambiguous double
 * fences and confuse parsers, so we rely solely on the frontmatter blocks:
 *
 *   # Rhesis Documentation (full)
 *
 *   ---
 *   url: https://docs.rhesis.ai/docs/getting-started
 *   title: Getting Started
 *   ---
 *   # Getting Started
 *   ...page body...
 *
 *   ---
 *   url: https://docs.rhesis.ai/docs/concepts
 *   title: Concepts
 *   ---
 *   ...
 *
 * Page order:  docs → guides → sdk → contribute → glossary → changelog
 * Glossary terms that are synthesized from glossary-terms.jsonl (and have no
 * MDX rawSource) are skipped — their content is in the primary glossary index.
 */

import { getAllPagesCached, SECTION_ORDER } from '../../lib/content-index.js'
import { cleanMdxToMarkdown } from '../../lib/mdx-to-markdown.js'
import { siteConfig } from '../../lib/site-config.js'

// ISR: regenerate at most once an hour. Origin still benefits from the
// in-memory page cache in content-index.js between revalidations.
export const revalidate = 3600

export async function GET() {
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

  const content = chunks.join('\n')

  return new Response(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
