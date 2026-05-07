/**
 * Tests for metadata helpers.
 *
 * Regression coverage for the root-page markdown alternate URL: the
 * .md alternate must be omitted for the root page (urlPath === '')
 * because `${siteUrl}.md` is not a valid URL.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { extractDescription, generatePageMetadata } from '../metadata.js'

test('extractDescription: strips YAML frontmatter before scanning', () => {
  const src = `---
title: Hello
description: from frontmatter
---

# Heading

This is the first real paragraph and it is long enough to be picked up by the description extractor heuristic.`
  const desc = extractDescription(src)
  assert.ok(desc)
  assert.match(desc, /first real paragraph/)
  assert.ok(!desc.includes('frontmatter'))
})

test('extractDescription: returns null for empty input', () => {
  assert.equal(extractDescription(''), null)
  assert.equal(extractDescription(null), null)
})

test('generatePageMetadata: includes .md alternate for child pages', () => {
  const meta = generatePageMetadata({ title: 'Foo' }, 'docs/foo')
  assert.equal(meta.alternates.canonical, 'https://docs.rhesis.ai/docs/foo')
  assert.deepEqual(meta.alternates.types, {
    'text/markdown': 'https://docs.rhesis.ai/docs/foo.md',
  })
})

test('generatePageMetadata: omits .md alternate for the root page', () => {
  // Regression: previously emitted "https://docs.rhesis.ai.md" which is
  // not a valid URL and not a route we serve.
  const meta = generatePageMetadata({ title: 'Home' }, '')
  assert.equal(meta.alternates.canonical, 'https://docs.rhesis.ai')
  assert.equal(
    meta.alternates.types,
    undefined,
    'root page must not advertise a malformed .md alternate'
  )
})
