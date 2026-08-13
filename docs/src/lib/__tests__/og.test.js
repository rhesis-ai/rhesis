/**
 * Tests for the generated social preview cards.
 *
 * The font assertions are the important ones: satori cannot read woff2, so the
 * cards depend on TTF subsets that live outside the normal font pipeline. If
 * one is renamed or dropped, every card silently becomes a redirect to the
 * static fallback image — these tests fail loudly instead.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { getOpenGraphImage, generatePageMetadata } from '../metadata.js'
import { resolveOgPage } from '../og-page.js'
import { titleFontSize, truncate, cardKey, OG_SIZE, OG_VERSION } from '../og-theme.js'
import { findContentDir, getMdxFiles, filePathToUrl } from '../content-index.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PUBLIC = path.join(__dirname, '../../public')

const OG_ASSETS = [
  'fonts/og/Sora-700.ttf',
  'fonts/og/Geist-400.ttf',
  'fonts/og/Geist-500.ttf',
  'fonts/og/GeistMono-500.ttf',
  'logo/rhesis-mark-og.png',
]

test('og assets: every font and image the card needs exists', () => {
  for (const asset of OG_ASSETS) {
    assert.ok(fs.existsSync(path.join(PUBLIC, asset)), `missing OG asset: ${asset}`)
  }
})

test('og assets: fonts are TTF, never woff2 — satori cannot decode woff2', () => {
  for (const asset of OG_ASSETS.filter(a => a.endsWith('.ttf'))) {
    const header = fs.readFileSync(path.join(PUBLIC, asset)).subarray(0, 4)
    // TrueType outlines start with 0x00010000; woff2 starts with "wOF2".
    assert.deepEqual([...header], [0x00, 0x01, 0x00, 0x00], `${asset} is not a plain TTF`)
  }
})

test('getOpenGraphImage: every page gets its own card URL', () => {
  const home = getOpenGraphImage('')
  const page = getOpenGraphImage('docs/endpoints')

  assert.equal(home, `https://docs.rhesis.ai/api/og?v=${OG_VERSION}`)
  assert.equal(page, `https://docs.rhesis.ai/api/og?p=docs%2Fendpoints&v=${OG_VERSION}`)
  assert.notEqual(home, page)
})

test('getOpenGraphImage: frontmatter ogImage wins over the generated card', () => {
  assert.equal(getOpenGraphImage('docs/tour', '/og/tour.png'), 'https://docs.rhesis.ai/og/tour.png')
  assert.equal(
    getOpenGraphImage('docs/tour', 'https://cdn.example.com/tour.png'),
    'https://cdn.example.com/tour.png'
  )
})

test('generatePageMetadata: openGraph and twitter point at the page card', () => {
  const meta = generatePageMetadata(
    { title: 'Endpoints', description: 'How to connect' },
    'docs/endpoints'
  )
  const expected = getOpenGraphImage('docs/endpoints', null, 'EndpointsHow to connect')

  assert.equal(meta.openGraph.images[0].url, expected)
  assert.equal(meta.twitter.images[0], expected)
  assert.equal(meta.openGraph.images[0].alt, 'Endpoints – Rhesis Documentation')
})

test('getOpenGraphImage: the card URL changes when the page text changes', () => {
  // Crawlers and the CDN cache by URL for a year, so an edited title or
  // description has to produce a different URL or the old card sticks.
  const before = generatePageMetadata({ title: 'Endpoints', description: 'old' }, 'docs/endpoints')
  const after = generatePageMetadata({ title: 'Endpoints', description: 'new' }, 'docs/endpoints')
  const again = generatePageMetadata({ title: 'Endpoints', description: 'old' }, 'docs/endpoints')

  assert.notEqual(before.openGraph.images[0].url, after.openGraph.images[0].url)
  assert.equal(before.openGraph.images[0].url, again.openGraph.images[0].url)
})

test('cardKey: stable, short, and collision-free across every page', () => {
  assert.equal(cardKey('same'), cardKey('same'))
  assert.match(cardKey('anything'), /^[0-9a-z]{7}$/)

  // A collision would pin two pages to one cached card.
  const keys = getMdxFiles(findContentDir())
    .map(filePathToUrl)
    .map(urlPath => {
      const page = resolveOgPage(urlPath)
      return cardKey(`${page.title}${page.description}`)
    })

  assert.equal(new Set(keys).size, keys.length)
})

test('resolveOgPage: resolves every content page', () => {
  const contentDir = findContentDir()
  assert.ok(contentDir, 'content directory not found')

  const unresolved = getMdxFiles(contentDir)
    .map(filePathToUrl)
    .filter(urlPath => !resolveOgPage(urlPath).found)

  assert.deepEqual(unresolved, [])
})

test('resolveOgPage: drops the brand suffix carried in frontmatter titles', () => {
  assert.equal(resolveOgPage('docs/endpoints').title, 'Endpoints')
  assert.equal(resolveOgPage('sdk/client').title, 'RhesisClient')
})

test('resolveOgPage: glossary terms use their exported definition, not raw MDX', () => {
  const term = resolveOgPage('glossary/llm-as-a-judge')

  assert.equal(term.section, 'Glossary')
  assert.ok(!term.description.includes('description:'), 'leaked the export block')
  assert.match(term.description, /^An approach where an LLM evaluates/)
})

test('resolveOgPage: keeps apostrophes in exported glossary definitions', () => {
  // The definitions are single-quoted JS strings, so `the AI\'s certainty`
  // must not be cut at the backslash.
  const term = resolveOgPage('glossary/confidence-score')

  assert.ok(!term.description.includes('\\'), `stray escape in: ${term.description}`)
  assert.match(term.description, /the AI's certainty/)
})

test('resolveOgPage: unknown paths fall back to the site card', () => {
  const missing = resolveOgPage('docs/nope/does-not-exist')

  assert.equal(missing.found, false)
  assert.equal(missing.title, 'Rhesis Documentation')
})

test('resolveOgPage: rejects path traversal', () => {
  assert.equal(resolveOgPage('../../../etc/passwd').found, false)
})

test('titleFontSize: steps down as the title grows', () => {
  const sizes = ['Tour', 'Adversarial Testing', 'Configure Telemetry: OTel GenAI Conventions'].map(
    titleFontSize
  )
  assert.deepEqual(
    [...sizes].sort((a, b) => b - a),
    sizes
  )
  assert.equal(OG_SIZE.width, 1200)
})

test('truncate: cuts on a word boundary and marks the cut', () => {
  assert.equal(truncate('short title', 40), 'short title')
  assert.equal(truncate('the quick brown fox jumps', 16), 'the quick brown…')
  assert.equal(truncate('  collapses   whitespace ', 40), 'collapses whitespace')
})
