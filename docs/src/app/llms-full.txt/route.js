/**
 * /llms-full.txt — full documentation corpus for LLM ingestion.
 *
 * The body is built by renderLlmsFullTxt() in lib/llm-views.js so it can be
 * unit-tested without Next.js runtime. Pages are delimited by their per-page
 * YAML frontmatter (no separate "---" separator).
 */

import { renderLlmsFullTxt } from '../../lib/llm-views.js'

// ISR: regenerate at most once an hour. Origin still benefits from the
// in-memory page cache in content-index.js between revalidations.
export const revalidate = 3600

export async function GET() {
  return new Response(renderLlmsFullTxt(), {
    status: 200,
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
