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
const glossaryDataPath = path.join(__dirname, '../content/glossary/glossary-terms.json')
const glossaryDir = path.join(__dirname, '../content/glossary')

// Read glossary data
const glossaryData = JSON.parse(fs.readFileSync(glossaryDataPath, 'utf8'))

console.log(`Generating pages for ${glossaryData.terms.length} glossary terms...`)

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
  
  console.log(`✓ Created ${term.id}/index.mdx`)
})

console.log(`\n✅ Successfully generated ${glossaryData.terms.length} glossary term pages!`)

