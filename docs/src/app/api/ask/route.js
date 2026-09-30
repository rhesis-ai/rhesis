/**
 * POST /api/ask — the "Ask the docs" widget's only backend.
 *
 * Forwards the question to the docs assistant service at ASK_DOCS_AGENT_URL (server-side
 * env, never sent to the browser). The logic lives in lib/ask-proxy.js so it can be
 * unit-tested without the Next.js runtime.
 */

import { proxyAsk } from '../../../lib/ask-proxy.js'

export const dynamic = 'force-dynamic'

export async function POST(request) {
  const body = await request.json().catch(() => null)
  const { status, body: payload } = await proxyAsk({
    method: 'POST',
    body,
    agentUrl: process.env.ASK_DOCS_AGENT_URL,
  })
  return Response.json(payload, { status, headers: { 'Cache-Control': 'no-store' } })
}
