/**
 * Server-side proxy from the "Ask the docs" widget to the docs assistant service.
 *
 * The browser only ever calls this site's /api/ask. This module forwards the question to the
 * assistant (ASK_DOCS_AGENT_URL, server-side only) and turns every failure into a short JSON
 * error the widget can show. Kept free of Next.js imports so it can be unit-tested directly.
 */

// Longer than the assistant's own 45 s turn timeout, so its fallback reply arrives first.
export const UPSTREAM_TIMEOUT_MS = 60_000

const UNAVAILABLE = {
  error: 'assistant_unavailable',
  message:
    "The docs assistant can't be reached right now. Try again in a moment, or search the docs.",
}

function result(status, body) {
  return { status, body }
}

function validMessage(body) {
  return body && typeof body.message === 'string' && body.message.trim() !== ''
}

/**
 * @param {object} options
 * @param {string} options.method  HTTP method of the incoming request
 * @param {object|null} options.body  parsed JSON body, or null when it wasn't JSON
 * @param {string|undefined} options.agentUrl  base URL of the docs assistant
 * @param {typeof fetch} [options.fetchImpl]
 * @param {number} [options.timeoutMs]
 * @returns {Promise<{status: number, body: object}>}
 */
export async function proxyAsk({
  method,
  body,
  agentUrl,
  fetchImpl = fetch,
  timeoutMs = UPSTREAM_TIMEOUT_MS,
}) {
  if (method !== 'POST') {
    return result(405, { error: 'method_not_allowed', message: 'Use POST.' })
  }
  if (!agentUrl) {
    return result(503, {
      error: 'assistant_unconfigured',
      message: "The docs assistant isn't set up on this site.",
    })
  }
  if (!validMessage(body)) {
    return result(400, {
      error: 'invalid_request',
      message: 'Send a JSON body with a non-empty "message".',
    })
  }

  let upstream
  try {
    upstream = await fetchImpl(`${agentUrl.replace(/\/+$/, '')}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: body.message,
        conversation_id: body.conversation_id ?? null,
      }),
      signal: AbortSignal.timeout(timeoutMs),
    })
  } catch {
    return result(502, UNAVAILABLE)
  }

  const payload = await upstream.json().catch(() => null)
  if (upstream.ok && payload) {
    return result(200, payload)
  }
  if (upstream.status === 503 && String(payload?.detail || '').startsWith('docs_unavailable')) {
    return result(503, {
      error: 'docs_unavailable',
      message: "The assistant can't reach the docs right now. Try again in a moment.",
    })
  }
  return result(upstream.status === 503 ? 503 : 502, UNAVAILABLE)
}
