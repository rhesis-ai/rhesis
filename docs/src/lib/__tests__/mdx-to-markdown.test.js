/**
 * Smoke tests for cleanMdxToMarkdown.
 *
 * Covers the contract used by /llms-full.txt and /<page>.md:
 *   - All MDX/JSX residue is stripped
 *   - Imports/exports never appear in the output
 *   - Fenced code blocks survive untouched (this is the most common
 *     correctness regression — the protect/restore step is fragile)
 *   - Prose `{id}` is preserved (the {expr} stripper is heuristic)
 *   - Frontmatter metadata is prepended when requested
 *
 * Run with:  npm test
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { cleanMdxToMarkdown } from '../mdx-to-markdown.js'

const SAMPLE_MDX = `---
title: Sample
description: Sample page
---

import { Foo } from '@/components/Foo'
import Bar from './Bar'
export const meta = { title: 'X' }

# Hello world

Some intro paragraph.

<CodeBlock language="bash">{\`npm install foo
npm run build\`}</CodeBlock>

Reference: PUT /test_results/{id} returns the result.

<NextStepCard
  emoji="🚀"
  title="Get started"
  description="Install and configure"
  link="/docs/getting-started"
/>

<Callout type="warning">
Be careful here.
</Callout>

<Tabs>
  <Tab title="One">
    Content of tab one.
  </Tab>
</Tabs>

<FeatureOverview features={[1, 2, 3]} />

A trailing paragraph with **bold** and *italic*.

\`\`\`python
def foo():
    return 42
\`\`\`
`

test('cleanMdxToMarkdown: empty input returns empty string', () => {
  assert.equal(cleanMdxToMarkdown(''), '')
  assert.equal(cleanMdxToMarkdown(null), '')
  assert.equal(cleanMdxToMarkdown(undefined), '')
})

test('cleanMdxToMarkdown: strips imports, exports, and YAML frontmatter', () => {
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.ok(!/^import\s/m.test(out), 'should not contain import lines')
  assert.ok(!/^export\s/m.test(out), 'should not contain export lines')
  assert.ok(!/^---\ntitle:/m.test(out), 'original YAML frontmatter should be removed')
})

test('cleanMdxToMarkdown: strips PascalCase JSX components', () => {
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.ok(!/<NextStepCard/.test(out), 'NextStepCard tag should be gone')
  assert.ok(!/<Tabs[\s>]/.test(out), 'Tabs tag should be gone')
  assert.ok(!/<Tab[\s>]/.test(out), 'Tab tag should be gone')
  assert.ok(!/<FeatureOverview/.test(out), 'FeatureOverview tag should be gone')
  assert.ok(!/<Callout/.test(out), 'Callout open tag should be gone')
  assert.ok(!/<\/Callout>/.test(out), 'Callout close tag should be gone')
  assert.ok(!/<CodeBlock/.test(out), 'CodeBlock tag should be gone')
})

test('cleanMdxToMarkdown: NextStepCard becomes a bullet link with description', () => {
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.match(out, /- \[Get started\]\(\/docs\/getting-started\): Install and configure/)
})

test('cleanMdxToMarkdown: Callout becomes a blockquote', () => {
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.match(out, /^>\s*Be careful here\./m)
})

test('cleanMdxToMarkdown: existing fenced code blocks survive intact', () => {
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.match(out, /```python\ndef foo\(\):\n {4}return 42\n```/)
})

test('cleanMdxToMarkdown: CodeBlock JSX becomes a fenced code block', () => {
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.match(out, /```bash\nnpm install foo\nnpm run build\n```/)
})

test('cleanMdxToMarkdown: preserves prose with {id}-style braces', () => {
  // This is the regression the tightened {expr} regex protects against.
  const out = cleanMdxToMarkdown(SAMPLE_MDX)
  assert.match(out, /PUT \/test_results\/\{id\}/)
})

test('cleanMdxToMarkdown: still strips real JSX expressions with operators/calls', () => {
  // The {expr} stripper only fires when the expression contains JS-specific
  // syntax (operators, calls, brackets, etc.). Plain identifiers like {id}
  // are preserved as prose.
  const src = [
    'Line A {getValue()} embedded.',
    'Line B {count > 5 && "many"} embedded.',
    'Line C {[1, 2, 3]} embedded.',
    'Line D {foo ? bar : baz} embedded.',
    '',
    'Another paragraph.',
  ].join('\n')
  const out = cleanMdxToMarkdown(src)
  assert.ok(!out.includes('{getValue()}'), 'function-call expression should be stripped')
  assert.ok(!out.includes('{count > 5'), 'logical-operator expression should be stripped')
  assert.ok(!out.includes('{[1, 2, 3]}'), 'array literal should be stripped')
  assert.ok(!out.includes('{foo ? bar : baz}'), 'ternary should be stripped')
})

test('cleanMdxToMarkdown: keeps Steps content as transparent wrapper', () => {
  const src = '<Steps>\n### Step 1\n\nDo a thing.\n\n### Step 2\n\nDo another.\n</Steps>'
  const out = cleanMdxToMarkdown(src)
  assert.ok(!out.includes('<Steps>'), 'Steps wrapper should be removed')
  assert.match(out, /### Step 1/)
  assert.match(out, /Do a thing\./)
  assert.match(out, /### Step 2/)
})

test('cleanMdxToMarkdown: prepends url/title frontmatter when meta is provided', () => {
  const out = cleanMdxToMarkdown('# Hello', {
    url: 'https://docs.rhesis.ai/foo',
    title: 'Foo',
  })
  assert.ok(out.startsWith('---\nurl: https://docs.rhesis.ai/foo\ntitle: Foo\n---\n'))
  assert.match(out, /# Hello/)
})

test('cleanMdxToMarkdown: collapses multiple blank lines', () => {
  const src = '# Hello\n\n\n\n\nWorld'
  const out = cleanMdxToMarkdown(src)
  assert.ok(!/\n{3,}/.test(out), 'should not contain three or more consecutive newlines')
})

test('cleanMdxToMarkdown: a-tag becomes a markdown link', () => {
  const src = 'See <a href="https://example.com">the example</a> for details.'
  const out = cleanMdxToMarkdown(src)
  assert.match(out, /\[the example\]\(https:\/\/example\.com\)/)
})
