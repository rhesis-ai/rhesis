/**
 * Serves any documentation page as clean markdown.
 *
 * This route is NOT meant to be called directly. Requests to
 * /<page>.md are rewritten by middleware to /api/md/<page>.
 *
 * Example:
 *   GET https://docs.rhesis.ai/docs/getting-started.md
 *   → rewritten → GET /api/md/docs/getting-started
 *   → responds   text/markdown with clean markdown of that page
 */

import { notFound } from 'next/navigation'
import { findContentDir, urlToFilePath } from '../../../../lib/content-index.js'
import { cleanMdxToMarkdown } from '../../../../lib/mdx-to-markdown.js'
import { siteConfig } from '../../../../lib/site-config.js'
import fs from 'fs'

export const dynamic = 'force-dynamic'

export async function GET(_request, { params }) {
  const { slug } = await params

  // Reconstruct the URL path from the slug array
  const urlPath = Array.isArray(slug) ? slug.join('/') : slug

  const contentDir = findContentDir()
  if (!contentDir) {
    return new Response('Documentation not available', { status: 503 })
  }

  const filePath = urlToFilePath(urlPath, contentDir)
  if (!filePath) {
    notFound()
  }

  let rawSource
  try {
    rawSource = fs.readFileSync(filePath, 'utf8')
  } catch {
    notFound()
  }

  const canonicalUrl = urlPath ? `${siteConfig.siteUrl}/${urlPath}` : siteConfig.siteUrl

  // Extract title from source for the frontmatter block
  const h1Match = rawSource.match(/^#\s+(.+)$/m)
  const title = h1Match ? h1Match[1].trim() : urlPath.split('/').pop()

  const markdown = cleanMdxToMarkdown(rawSource, { url: canonicalUrl, title })

  return new Response(markdown, {
    status: 200,
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
