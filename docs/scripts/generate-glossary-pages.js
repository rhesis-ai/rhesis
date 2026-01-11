#!/usr/bin/env node

/**
 * Script to generate individual glossary term pages from glossary-terms.json
 * Run with: node scripts/generate-glossary-pages.js
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Paths
const glossaryDataPath = path.join(__dirname, '../content/glossary/glossary-terms.jsonl')
const glossaryDir = path.join(__dirname, '../content/glossary')

// Read and parse JSONL data (one JSON object per line)
const glossaryDataRaw = fs.readFileSync(glossaryDataPath, 'utf8')
const glossaryData = {
  terms: glossaryDataRaw
    .trim()
    .split('\n')
    .map(line => JSON.parse(line))
}

// Clean up old term directories before generating new ones
console.log('Cleaning up old glossary pages...')
const currentTermIds = new Set(glossaryData.terms.map(t => t.id))
const filesInGlossary = fs.readdirSync(glossaryDir)

// Files/directories to preserve
const preservedItems = new Set([
  'index.mdx',
  'glossary-terms.jsonl',
  '.README.md',
  'README.md',
  '_meta.tsx'
])

filesInGlossary.forEach(item => {
  const itemPath = path.join(glossaryDir, item)
  const isDirectory = fs.statSync(itemPath).isDirectory()
  
  // Only clean up directories that aren't in the current term list
  if (isDirectory && !currentTermIds.has(item) && !preservedItems.has(item)) {
    console.log(`  Removing old directory: ${item}`)
    fs.rmSync(itemPath, { recursive: true, force: true })
  }
})

console.log(`\nGenerating pages for ${glossaryData.terms.length} glossary terms...`)

// Generate a page for each term
glossaryData.terms.forEach(term => {
  const termDir = path.join(glossaryDir, term.id)
  
  // Create directory if it doesn't exist
  if (!fs.existsSync(termDir)) {
    fs.mkdirSync(termDir, { recursive: true })
  }

  // Generate MDX content
  const mdxContent = `import { GlossaryTermPage } from '@/components/glossary/GlossaryTermPage'

export const metadata = {
  title: '${term.term} - Glossary',
  description: '${term.definition.replace(/'/g, "\\'")}',
}

# ${term.term}

<GlossaryTermPage termId="${term.id}" />
`

  // Write the MDX file
  const mdxPath = path.join(termDir, 'index.mdx')
  fs.writeFileSync(mdxPath, mdxContent, 'utf8')
})

console.log(`\n✅ Successfully generated ${glossaryData.terms.length} glossary term pages!`)

// Generate _meta.tsx to hide all term pages from navigation
console.log('\nGenerating _meta.tsx...')

const metaContent = `export default {
  index: "Terms",
${glossaryData.terms.map(term => `  "${term.id}": {
    display: "hidden",
  },`).join('\n')}
};
`

const metaPath = path.join(glossaryDir, '_meta.tsx')
fs.writeFileSync(metaPath, metaContent, 'utf8')
console.log(`✓ Created _meta.tsx with ${glossaryData.terms.length} hidden term entries`)

