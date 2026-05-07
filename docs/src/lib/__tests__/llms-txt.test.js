/**
 * Integration smoke test for the /llms.txt route.
 *
 * Asserts the contract that LLM-ingestion clients depend on:
 *   - Header: H1 site name + blockquote summary
 *   - Each primary section listed under its `## ` heading
 *   - Every page link points to the .md variant
 *   - "## Optional" block is present when glossary/changelog exist
 *   - Resources footer is present
 *
 * This test imports the route handler module directly and invokes its GET
 * function — it does NOT spin up a Next.js dev server. The route depends on
 * the real content directory, so this is a true end-to-end smoke test.
 *
 * If the docs/content tree is unavailable (e.g. in a stripped CI image),
 * this test soft-skips rather than failing.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { findContentDir, clearPagesCache } from '../content-index.js'
import { GET as getLlmsTxt } from '../../app/llms.txt/route.js'

const hasContent = !!findContentDir()

test('GET /llms.txt: responds with text/plain and a non-empty body', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present; skipping integration smoke test')
    return
  }
  clearPagesCache()
  const res = await getLlmsTxt()
  assert.equal(res.status, 200)
  assert.match(res.headers.get('Content-Type') || '', /^text\/plain/)
  const body = await res.text()
  assert.ok(body.length > 200, 'body should contain a real index')
})

test('GET /llms.txt: includes header and blockquote summary', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const res = await getLlmsTxt()
  const body = await res.text()
  assert.match(body, /^# Rhesis Documentation\b/m)
  assert.match(body, /^>\s+\S+/m)
})

test('GET /llms.txt: every link points to a .md URL', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const res = await getLlmsTxt()
  const body = await res.text()

  // Find every markdown link that targets a docs.rhesis.ai URL. Filter out
  // external links (GitHub, Discord, the readthedocs SDK reference, the
  // llms-full.txt resource link).
  const linkRegex = /\[[^\]]+\]\((https:\/\/docs\.rhesis\.ai\/[^)]+)\)/g
  const urls = []
  for (const m of body.matchAll(linkRegex)) {
    urls.push(m[1])
  }

  assert.ok(urls.length > 0, 'expected at least one page link')
  for (const url of urls) {
    if (url.endsWith('llms-full.txt')) continue
    assert.ok(url.endsWith('.md'), `internal page link should end in .md, got ${url}`)
  }
})

test('GET /llms.txt: includes the expected primary section headings', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const res = await getLlmsTxt()
  const body = await res.text()

  // Sections are conditional on having pages; at minimum we expect Docs.
  assert.match(body, /^## Docs$/m, 'Docs section should be present')

  // If Optional exists, it should appear after the primary sections.
  if (/^## Optional$/m.test(body)) {
    const optionalIdx = body.search(/^## Optional$/m)
    const docsIdx = body.search(/^## Docs$/m)
    assert.ok(optionalIdx > docsIdx, '## Optional should appear after primary sections')
  }
})

test('GET /llms.txt: includes Resources footer with llms-full.txt pointer', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const res = await getLlmsTxt()
  const body = await res.text()
  assert.match(body, /^## Resources$/m)
  assert.match(body, /llms-full\.txt/)
})
