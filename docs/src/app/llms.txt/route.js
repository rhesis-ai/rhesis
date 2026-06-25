/**
 * /llms.txt — machine-readable site index for LLMs.
 *
 * Format follows https://llmstxt.org/. The body is built by renderLlmsTxt()
 * in lib/llm-views.js so it can be unit-tested without Next.js runtime.
 */

import { renderLlmsTxt } from '../../lib/llm-views.js'

// ISR: regenerate at most once an hour. Origin still benefits from the
// in-memory page cache in content-index.js between revalidations.
export const revalidate = 3600

export async function GET() {
  return new Response(renderLlmsTxt(), {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
