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

import { findContentDir, urlToFilePath } from '../../../../lib/content-index.js'
import { cleanMdxToMarkdown } from '../../../../lib/mdx-to-markdown.js'
import { siteConfig } from '../../../../lib/site-config.js'
import fs from 'fs'

// ISR: per-page markdown is build-time content; revalidate hourly.
export const revalidate = 3600

/** 404 with text/markdown body so clients that asked for .md get markdown back. */
function notFoundResponse() {
  return new Response('# 404\n\nPage not found.\n', {
    status: 404,
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  })
}

export async function GET(_request, { params }) {
  // In Next.js 15, `params` is a Promise in route handlers (async request
  // APIs). Awaiting is required.
  const { slug } = await params

  // Reconstruct the URL path from the slug array
  const urlPath = Array.isArray(slug) ? slug.join('/') : slug

  const contentDir = findContentDir()
  if (!contentDir) {
    return new Response('# 503\n\nDocumentation not available.\n', {
      status: 503,
      headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
    })
  }

  const filePath = urlToFilePath(urlPath, contentDir)
  if (!filePath) return notFoundResponse()

  let rawSource
  try {
    rawSource = fs.readFileSync(filePath, 'utf8')
  } catch {
    return notFoundResponse()
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
