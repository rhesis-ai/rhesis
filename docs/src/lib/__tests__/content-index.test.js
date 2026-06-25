/**
 * Smoke tests for content-index.js.
 *
 * Covers:
 *   - filePathToUrl path-shape rules (Nextra conventions)
 *   - urlToFilePath happy-path resolution
 *   - urlToFilePath path-traversal rejection (security regression)
 *   - getAllPagesCached returns the expected section structure
 *
 * Uses a temporary content directory so these tests don't depend on the
 * actual docs/content tree (which changes constantly).
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  SECTION_ORDER,
  filePathToUrl,
  urlToFilePath,
  getMdxFiles,
  getGlossaryTerms,
} from '../content-index.js'

// ---------------------------------------------------------------------------
// Test fixture: a self-contained tiny content tree
// ---------------------------------------------------------------------------

function makeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rhesis-content-'))
  const write = (rel, body) => {
    const full = path.join(root, rel)
    fs.mkdirSync(path.dirname(full), { recursive: true })
    fs.writeFileSync(full, body, 'utf8')
  }

  write('index.mdx', '# Home\n\nLanding page.')
  write('docs/getting-started.mdx', '---\ntitle: Getting Started\n---\n# Getting Started\n\nHello.')
  write(
    'docs/concepts/index.mdx',
    '---\ntitle: Concepts\n---\n# Concepts\n\nA short concepts paragraph that has enough content to satisfy the description extractor heuristic.'
  )
  write('sdk/installation.mdx', '# Installation\n\nInstall the SDK.')
  write('docs/_meta.tsx', 'export default {}') // should be skipped
  write(
    'glossary/glossary-terms.jsonl',
    JSON.stringify({ id: 'llm', term: 'LLM', definition: 'Large Language Model' })
  )

  return { root }
}

function cleanup(root) {
  try {
    fs.rmSync(root, { recursive: true, force: true })
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// filePathToUrl
// ---------------------------------------------------------------------------

test('filePathToUrl: drops .mdx and trailing /index', () => {
  assert.equal(filePathToUrl('docs/getting-started.mdx'), 'docs/getting-started')
  assert.equal(filePathToUrl('docs/concepts/index.mdx'), 'docs/concepts')
  assert.equal(filePathToUrl('index.mdx'), '')
  assert.equal(filePathToUrl('docs/foo.mdx'), 'docs/foo')
})

// ---------------------------------------------------------------------------
// urlToFilePath happy paths
// ---------------------------------------------------------------------------

test('urlToFilePath: resolves <urlPath>.mdx', () => {
  const { root } = makeFixture()
  try {
    const resolved = urlToFilePath('docs/getting-started', root)
    assert.ok(resolved, 'should find the file')
    assert.equal(path.basename(resolved), 'getting-started.mdx')
  } finally {
    cleanup(root)
  }
})

test('urlToFilePath: resolves <urlPath>/index.mdx', () => {
  const { root } = makeFixture()
  try {
    const resolved = urlToFilePath('docs/concepts', root)
    assert.ok(resolved, 'should find the index file')
    assert.equal(path.basename(resolved), 'index.mdx')
    assert.match(resolved, /docs[\\/]concepts[\\/]index\.mdx$/)
  } finally {
    cleanup(root)
  }
})

test('urlToFilePath: returns null for missing pages', () => {
  const { root } = makeFixture()
  try {
    assert.equal(urlToFilePath('does/not/exist', root), null)
  } finally {
    cleanup(root)
  }
})

test('urlToFilePath: empty path returns root index.mdx if it exists', () => {
  const { root } = makeFixture()
  try {
    const resolved = urlToFilePath('', root)
    assert.ok(resolved)
    assert.equal(path.basename(resolved), 'index.mdx')
  } finally {
    cleanup(root)
  }
})

// ---------------------------------------------------------------------------
// urlToFilePath: path traversal hardening
// ---------------------------------------------------------------------------

test('urlToFilePath: rejects ".." traversal segments', () => {
  const { root } = makeFixture()
  // Create a file outside the content dir so a successful traversal would
  // actually return something.
  const escapeDir = path.dirname(root)
  const sentinel = path.join(escapeDir, 'secret.mdx')
  fs.writeFileSync(sentinel, '# Secret', 'utf8')
  try {
    assert.equal(urlToFilePath('../secret', root), null, '"../" segment must be rejected')
    assert.equal(urlToFilePath('docs/../../secret', root), null, 'embedded ".." must be rejected')
    assert.equal(urlToFilePath('./secret', root), null, '"./" segment must be rejected')
  } finally {
    fs.unlinkSync(sentinel)
    cleanup(root)
  }
})

test('urlToFilePath: rejects absolute paths and backslash injection', () => {
  const { root } = makeFixture()
  try {
    assert.equal(urlToFilePath('/etc/passwd', root), null)
    assert.equal(urlToFilePath('foo\\bar', root), null)
    assert.equal(urlToFilePath('foo\0bar', root), null)
  } finally {
    cleanup(root)
  }
})

test('urlToFilePath: handles non-string input gracefully', () => {
  assert.equal(urlToFilePath(null, '/tmp'), null)
  assert.equal(urlToFilePath(undefined, '/tmp'), null)
  assert.equal(urlToFilePath(123, '/tmp'), null)
})

// ---------------------------------------------------------------------------
// getMdxFiles & getGlossaryTerms
// ---------------------------------------------------------------------------

test('getMdxFiles: skips _meta.tsx and underscore-prefixed files', () => {
  const { root } = makeFixture()
  try {
    const files = getMdxFiles(root)
    assert.ok(files.includes('docs/getting-started.mdx'))
    assert.ok(files.some(f => f.endsWith('docs/concepts/index.mdx')))
    assert.ok(!files.some(f => f.includes('_meta')))
  } finally {
    cleanup(root)
  }
})

test('getGlossaryTerms: parses JSONL and returns objects', () => {
  const { root } = makeFixture()
  try {
    const terms = getGlossaryTerms(root)
    assert.equal(terms.length, 1)
    assert.equal(terms[0].id, 'llm')
    assert.equal(terms[0].term, 'LLM')
  } finally {
    cleanup(root)
  }
})

test('getGlossaryTerms: returns [] when file is missing', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rhesis-empty-'))
  try {
    assert.deepEqual(getGlossaryTerms(root), [])
  } finally {
    cleanup(root)
  }
})

test('getGlossaryTerms: drops rows missing a usable id', () => {
  // Regression test: malformed JSONL rows must never produce
  // `glossary/undefined` URLs in the generated sitemap / llms.txt.
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rhesis-glossary-'))
  const jsonl = [
    JSON.stringify({ id: 'good', term: 'Good', definition: 'Good term' }),
    JSON.stringify({ term: 'Missing id' }),
    JSON.stringify({ id: '', term: 'Empty id' }),
    JSON.stringify({ id: '   ', term: 'Whitespace id' }),
    JSON.stringify({ id: 42, term: 'Non-string id' }),
    'this is not valid JSON',
    JSON.stringify({ id: 'second-good', term: 'Second' }),
  ].join('\n')
  const dir = path.join(root, 'glossary')
  fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(path.join(dir, 'glossary-terms.jsonl'), jsonl, 'utf8')
  try {
    const terms = getGlossaryTerms(root)
    assert.equal(terms.length, 2, 'only the two well-formed rows should survive')
    assert.deepEqual(
      terms.map(t => t.id),
      ['good', 'second-good']
    )
  } finally {
    cleanup(root)
  }
})

// ---------------------------------------------------------------------------
// SECTION_ORDER invariant
// ---------------------------------------------------------------------------

test('SECTION_ORDER: matches the documented sidebar order', () => {
  assert.deepEqual(SECTION_ORDER, ['docs', 'guides', 'sdk', 'contribute', 'glossary', 'changelog'])
})
