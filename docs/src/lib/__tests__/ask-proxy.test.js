/**
 * Tests for proxyAsk() — the logic behind POST /api/ask.
 *
 * Covers:
 *   - forwarding the message and conversation id to <agent>/chat
 *   - rejecting non-POST, missing config and bad bodies before any upstream call
 *   - mapping upstream failures (network, timeout, 5xx, docs down) to friendly errors
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { proxyAsk } from '../ask-proxy.js'

const AGENT = 'http://agent.local:8893/'

function fakeFetch(response) {
  const calls = []
  const impl = async (url, init) => {
    calls.push({ url, init })
    if (response instanceof Error) throw response
    return response
  }
  return { impl, calls }
}

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

test('proxyAsk: forwards the question to /chat and returns the answer', async () => {
  const answer = { route: 'answered', response: 'Yes.', citations: [] }
  const { impl, calls } = fakeFetch(jsonResponse(200, answer))

  const result = await proxyAsk({
    method: 'POST',
    body: { message: 'How do I install the SDK?', conversation_id: 'c1', extra: 'dropped' },
    agentUrl: AGENT,
    fetchImpl: impl,
  })

  assert.equal(result.status, 200)
  assert.deepEqual(result.body, answer)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, 'http://agent.local:8893/chat')
  assert.equal(calls[0].init.method, 'POST')
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    message: 'How do I install the SDK?',
    conversation_id: 'c1',
  })
})

test('proxyAsk: sends a null conversation id when none is given', async () => {
  const { impl, calls } = fakeFetch(jsonResponse(200, { route: 'answered' }))
  await proxyAsk({ method: 'POST', body: { message: 'hi' }, agentUrl: AGENT, fetchImpl: impl })
  assert.equal(JSON.parse(calls[0].init.body).conversation_id, null)
})

test('proxyAsk: only POST is allowed', async () => {
  const { impl, calls } = fakeFetch(jsonResponse(200, {}))
  const result = await proxyAsk({ method: 'GET', body: null, agentUrl: AGENT, fetchImpl: impl })
  assert.equal(result.status, 405)
  assert.equal(calls.length, 0)
})

test('proxyAsk: missing agent URL is a 503 without an upstream call', async () => {
  const { impl, calls } = fakeFetch(jsonResponse(200, {}))
  const result = await proxyAsk({
    method: 'POST',
    body: { message: 'hi' },
    agentUrl: undefined,
    fetchImpl: impl,
  })
  assert.equal(result.status, 503)
  assert.equal(result.body.error, 'assistant_unconfigured')
  assert.equal(calls.length, 0)
})

test('proxyAsk: rejects bodies without a message', async () => {
  const { impl, calls } = fakeFetch(jsonResponse(200, {}))
  for (const body of [null, {}, { message: '   ' }, { message: 42 }]) {
    const result = await proxyAsk({ method: 'POST', body, agentUrl: AGENT, fetchImpl: impl })
    assert.equal(result.status, 400, JSON.stringify(body))
    assert.equal(result.body.error, 'invalid_request')
  }
  assert.equal(calls.length, 0)
})

test('proxyAsk: a network failure becomes a friendly 502', async () => {
  const { impl } = fakeFetch(new TypeError('fetch failed'))
  const result = await proxyAsk({
    method: 'POST',
    body: { message: 'hi' },
    agentUrl: AGENT,
    fetchImpl: impl,
  })
  assert.equal(result.status, 502)
  assert.equal(result.body.error, 'assistant_unavailable')
  assert.match(result.body.message, /can't be reached/)
})

test('proxyAsk: an upstream timeout becomes a friendly 502', async () => {
  const hang = (_url, init) =>
    new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(init.signal.reason))
    })
  const result = await proxyAsk({
    method: 'POST',
    body: { message: 'hi' },
    agentUrl: AGENT,
    fetchImpl: hang,
    timeoutMs: 10,
  })
  assert.equal(result.status, 502)
  assert.equal(result.body.error, 'assistant_unavailable')
})

test('proxyAsk: docs down upstream is reported as docs_unavailable', async () => {
  const { impl } = fakeFetch(
    jsonResponse(503, { detail: "docs_unavailable: the docs site can't be reached" })
  )
  const result = await proxyAsk({
    method: 'POST',
    body: { message: 'hi' },
    agentUrl: AGENT,
    fetchImpl: impl,
  })
  assert.equal(result.status, 503)
  assert.equal(result.body.error, 'docs_unavailable')
})

test('proxyAsk: other upstream errors never leak their details', async () => {
  for (const status of [500, 404, 503]) {
    const { impl } = fakeFetch(jsonResponse(status, { detail: 'internal stack trace' }))
    const result = await proxyAsk({
      method: 'POST',
      body: { message: 'hi' },
      agentUrl: AGENT,
      fetchImpl: impl,
    })
    assert.equal(result.status, status === 503 ? 503 : 502)
    assert.equal(result.body.error, 'assistant_unavailable')
    assert.ok(!JSON.stringify(result.body).includes('stack trace'))
  }
})
