/**
 * /llms-full.txt — full documentation corpus for LLM ingestion.
 *
 * Concatenates every page's cleaned markdown, separated by comment delimiters
 * that make it easy for an LLM to identify page boundaries:
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
 *   ...
 *
 * Page order:  docs → guides → sdk → contribute → glossary → changelog
 * Glossary terms that are synthesized from glossary-terms.jsonl (and have no
 * MDX rawSource) are skipped — their content is in the primary glossary index.
 */

import { getAllPages, SECTION_ORDER } from '../../lib/content-index.js'
import { cleanMdxToMarkdown } from '../../lib/mdx-to-markdown.js'
import { siteConfig } from '../../lib/site-config.js'

export const dynamic = 'force-dynamic'

export async function GET() {
  const { bySection } = getAllPages()

  const chunks = []

  chunks.push(`# ${siteConfig.siteName} (full)`)
  chunks.push('')
  chunks.push(`> ${siteConfig.siteDescription}`)
  chunks.push('')
  chunks.push(
    `> This file contains the complete documentation corpus for LLM ingestion.`
  )
  chunks.push(
    `> For a curated index with links, see ${siteConfig.siteUrl}/llms.txt`
  )
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
      chunks.push('---')
      chunks.push('')
    }
  }

  const content = chunks.join('\n')

  return new Response(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
