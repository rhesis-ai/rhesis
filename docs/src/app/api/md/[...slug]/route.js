/**
 * Serves any documentation page as clean markdown.
 *
 * This route is NOT meant to be called directly. Requests to /<page>.md are
 * rewritten by middleware to /api/md/<page>. The actual rendering logic
 * lives in lib/llm-views.js so it can be unit-tested without Next.js runtime.
 *
 * Example:
 *   GET https://docs.rhesis.ai/docs/getting-started.md
 *   → rewritten → GET /api/md/docs/getting-started
 *   → responds   text/markdown with clean markdown of that page
 */

import { renderPageMarkdown } from '../../../../lib/llm-views.js'

// ISR: per-page markdown is build-time content; revalidate hourly.
export const revalidate = 3600

const MARKDOWN_HEADERS = {
  'Content-Type': 'text/markdown; charset=utf-8',
  'Cache-Control': 'public, max-age=3600, s-maxage=3600',
}

export async function GET(_request, { params }) {
  // In Next.js 15, `params` is a Promise in route handlers (async request
  // APIs). Awaiting is required.
  const { slug } = await params
  const urlPath = Array.isArray(slug) ? slug.join('/') : slug || ''

  const result = renderPageMarkdown(urlPath)

  if (result.status === 200) {
    return new Response(result.body, { status: 200, headers: MARKDOWN_HEADERS })
  }
  if (result.status === 503) {
    return new Response('# 503\n\nDocumentation not available.\n', {
      status: 503,
      headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
    })
  }
  return new Response('# 404\n\nPage not found.\n', {
    status: 404,
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  })
}
