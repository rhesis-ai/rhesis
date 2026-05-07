/**
 * Integration tests for the /api/md/[...slug] route handler.
 *
 * Covers:
 *   - 200 response with text/markdown for a known page
 *   - 404 with a markdown body for unknown pages
 *   - 404 for path-traversal attempts (defense-in-depth check on top of
 *     urlToFilePath's own sanitization)
 *
 * Soft-skips when docs/content is unavailable.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { findContentDir, getAllPagesCached, clearPagesCache } from '../content-index.js'
import { GET as getMd } from '../../app/api/md/[...slug]/route.js'

const hasContent = !!findContentDir()

/** Helper: invoke the route handler with a slug array. */
async function call(slugArray) {
  return getMd(new Request('http://test/'), { params: Promise.resolve({ slug: slugArray }) })
}

test('GET /api/md/...: serves a known page as text/markdown', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  clearPagesCache()
  const { all } = getAllPagesCached()
  const sample = all.find(p => p.rawSource && p.urlPath)
  if (!sample) {
    t.skip('no usable sample page found in content tree')
    return
  }

  const res = await call(sample.urlPath.split('/'))
  assert.equal(res.status, 200)
  assert.match(res.headers.get('Content-Type') || '', /^text\/markdown/)
  const body = await res.text()
  assert.ok(body.startsWith('---\nurl: '), 'body should begin with frontmatter')
  assert.match(body, new RegExp(`url:\\s+https://docs\\.rhesis\\.ai/${sample.urlPath}\\b`))
})

test('GET /api/md/...: returns 404 markdown for unknown pages', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  const res = await call(['this', 'page', 'does', 'not', 'exist'])
  assert.equal(res.status, 404)
  assert.match(res.headers.get('Content-Type') || '', /^text\/markdown/)
  assert.match(await res.text(), /404/)
})

test('GET /api/md/...: rejects path-traversal slugs with 404', async t => {
  if (!hasContent) {
    t.skip('docs/content directory not present')
    return
  }
  // Even if Next's router didn't normalize the slug, urlToFilePath must
  // refuse to resolve outside contentDir.
  const cases = [['..', 'etc', 'passwd'], ['docs', '..', '..', 'secret'], ['/abs/path']]
  for (const slug of cases) {
    const res = await call(slug)
    assert.equal(res.status, 404, `traversal slug ${JSON.stringify(slug)} must 404`)
  }
})
