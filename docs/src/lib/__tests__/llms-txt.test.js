/**
 * Smoke tests for the renderLlmsTxt() / renderLlmsFullTxt() lib helpers.
 *
 * These functions back the /llms.txt and /llms-full.txt routes; the route
 * handlers themselves are thin Response wrappers so we exercise the logic
 * here at the lib level (no Next.js runtime required).
 *
 * Asserts the contract that LLM-ingestion clients depend on:
 *   - Header: H1 site name + blockquote summary
 *   - Each primary section listed under its `## ` heading
 *   - Every page link points to the .md variant
 *   - "## Optional" block is present when glossary/changelog exist
 *   - Resources footer is present
 *   - llms-full.txt has no double "---" page boundary
 *
 * Soft-skips when docs/content is unavailable.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { findContentDir, clearPagesCache } from '../content-index.js'
import { renderLlmsTxt, renderLlmsFullTxt } from '../llm-views.js'

const hasContent = !!findContentDir()

test('renderLlmsTxt: returns a non-empty string', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present; skipping integration smoke test')
    return
  }
  clearPagesCache()
  const body = renderLlmsTxt()
  assert.equal(typeof body, 'string')
  assert.ok(body.length > 200, 'body should contain a real index')
})

test('renderLlmsTxt: includes header and blockquote summary', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const body = renderLlmsTxt()
  assert.match(body, /^# Rhesis Documentation\b/m)
  assert.match(body, /^>\s+\S+/m)
})

test('renderLlmsTxt: every internal link points to a .md URL', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const body = renderLlmsTxt()

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

test('renderLlmsTxt: includes the expected primary section headings', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const body = renderLlmsTxt()

  // At minimum we expect Docs.
  assert.match(body, /^## Docs$/m, 'Docs section should be present')
  assert.match(body, /^## For AI agents$/m, 'Agent section should be present')

  if (/^## Optional$/m.test(body)) {
    const optionalIdx = body.search(/^## Optional$/m)
    const docsIdx = body.search(/^## Docs$/m)
    assert.ok(optionalIdx > docsIdx, '## Optional should appear after primary sections')
  }
})

test('renderLlmsTxt: includes Resources footer with llms-full.txt pointer', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const body = renderLlmsTxt()
  assert.match(body, /^## Resources$/m)
  assert.match(body, /llms-full\.txt/)
})

// ---------------------------------------------------------------------------
// renderLlmsFullTxt
// ---------------------------------------------------------------------------

test('renderLlmsFullTxt: returns a substantial markdown corpus', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const body = renderLlmsFullTxt()
  assert.equal(typeof body, 'string')
  // The corpus is ~1 MB in production. Use a low floor so the test is robust
  // to content tree size changes.
  assert.ok(body.length > 5000, `corpus should be substantial, got ${body.length} bytes`)
  assert.match(body, /^# Rhesis Documentation \(full\)$/m)
})

test('renderLlmsFullTxt: pages are delimited by frontmatter (no double "---")', t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const body = renderLlmsFullTxt()
  // An empty fence (---\n\s*\n---) with no key/value rows would mean we still
  // have the redundant separator. Frontmatter blocks always start with
  // "url:" or "title:" on the next line, so this regex catches the bug.
  const emptyFence = /\n---\n\s*\n---\n(?!url:|title:)/
  assert.ok(
    !emptyFence.test(body),
    'llms-full.txt should not contain empty/redundant --- separators between pages'
  )
})
