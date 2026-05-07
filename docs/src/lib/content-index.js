/**
 * Shared content scanner for the Rhesis docs site.
 * Single source of truth used by sitemap, llms.txt, llms-full.txt, and the .md route.
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { extractDescription } from './metadata.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

/** Ordered list of top-level sections matching the sidebar / _meta.tsx order. */
export const SECTION_ORDER = ['docs', 'guides', 'sdk', 'contribute', 'glossary', 'changelog']

/** Human-readable labels for each section. */
export const SECTION_LABELS = {
  docs: 'Docs',
  guides: 'Guides',
  sdk: 'SDK',
  contribute: 'Contribute',
  glossary: 'Glossary',
  changelog: 'Changelog',
}

/**
 * Sections placed under "Optional" in llms.txt so the primary index stays
 * short enough to fit in a context window.
 */
export const OPTIONAL_SECTIONS = new Set(['glossary', 'changelog'])

// ---------------------------------------------------------------------------
// Filesystem helpers
// ---------------------------------------------------------------------------

/** Finds the content directory, trying several candidate paths. */
export function findContentDir() {
  const candidates = [
    path.join(__dirname, '../../content'), // docs/src/lib -> docs/content
    path.join(process.cwd(), 'content'), // Docker / production CWD
    path.join(__dirname, '../../../content'), // alternative layout
  ]
  for (const dir of candidates) {
    try {
      if (fs.existsSync(dir)) return dir
    } catch {
      // try next
    }
  }
  return null
}

/**
 * Recursively scans a directory for .mdx files.
 * Skips hidden dirs, node_modules, and files starting with `_`.
 *
 * @param {string} dir
 * @param {string} baseDir - Base for computing relative paths (defaults to dir)
 * @returns {string[]} Relative file paths
 */
export function getMdxFiles(dir, baseDir = dir) {
  const files = []
  try {
    const items = fs.readdirSync(dir, { withFileTypes: true })
    for (const item of items) {
      const fullPath = path.join(dir, item.name)
      if (item.isDirectory()) {
        if (!item.name.startsWith('.') && item.name !== 'node_modules') {
          files.push(...getMdxFiles(fullPath, baseDir))
        }
      } else if (item.isFile() && item.name.endsWith('.mdx') && !item.name.startsWith('_')) {
        files.push(path.relative(baseDir, fullPath))
      }
    }
  } catch {
    // directory not readable
  }
  return files
}

/**
 * Converts a relative .mdx file path to a URL path.
 * e.g. "docs/getting-started/index.mdx" -> "docs/getting-started"
 *      "docs/concepts.mdx"              -> "docs/concepts"
 *      "index.mdx"                       -> "" (root)
 */
export function filePathToUrl(filePath) {
  let urlPath = filePath.replace(/\.mdx$/, '').replace(/\\/g, '/')
  urlPath = urlPath.replace(/\/index$/, '')
  if (!urlPath || urlPath === 'index') return ''
  return urlPath
}

/**
 * Resolves a URL path back to an absolute .mdx file path, or null if not found.
 * Tries "<urlPath>.mdx" first, then "<urlPath>/index.mdx".
 *
 * @param {string} urlPath - e.g. "docs/getting-started"
 * @param {string} contentDir
 * @returns {string|null}
 */
export function urlToFilePath(urlPath, contentDir) {
  if (!urlPath) {
    const p = path.join(contentDir, 'index.mdx')
    return fs.existsSync(p) ? p : null
  }
  const direct = path.join(contentDir, `${urlPath}.mdx`)
  if (fs.existsSync(direct)) return direct
  const index = path.join(contentDir, urlPath, 'index.mdx')
  if (fs.existsSync(index)) return index
  return null
}

// ---------------------------------------------------------------------------
// Page loading
// ---------------------------------------------------------------------------

function extractTitleFromSource(source) {
  const m = source.match(/^#\s+(.+)$/m)
  return m ? m[1].trim() : null
}

function humanizeSlug(slug) {
  const name = (slug || '').split('/').pop() || 'Home'
  return name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function getSection(urlPath) {
  if (!urlPath) return 'docs'
  const first = urlPath.split('/')[0]
  return SECTION_ORDER.includes(first) ? first : 'docs'
}

/**
 * Loads a single page from a relative file path.
 *
 * @param {string} filePath - Relative path within contentDir (e.g. "docs/concepts.mdx")
 * @param {string} contentDir
 * @returns {{ urlPath, title, description, section, rawSource } | null}
 */
export function loadPage(filePath, contentDir) {
  const fullPath = path.join(contentDir, filePath)
  let rawSource
  try {
    rawSource = fs.readFileSync(fullPath, 'utf8')
  } catch {
    return null
  }

  const urlPath = filePathToUrl(filePath)
  const section = getSection(urlPath)

  // Title: YAML frontmatter > first H1 > humanized slug
  let title = null
  const fmMatch = rawSource.match(/^---\n([\s\S]*?)\n---/)
  if (fmMatch) {
    const titleLine = fmMatch[1].match(/^title:\s*(.+)$/m)
    if (titleLine) title = titleLine[1].trim().replace(/^['"]|['"]$/g, '')
  }
  if (!title) title = extractTitleFromSource(rawSource)
  if (!title) title = humanizeSlug(urlPath)

  const description = extractDescription(rawSource)

  return { urlPath, title, description, section, rawSource }
}

// ---------------------------------------------------------------------------
// Glossary helpers
// ---------------------------------------------------------------------------

/**
 * Reads the pre-built glossary-terms.jsonl and returns parsed term objects.
 * Returns [] if the file is missing (e.g. before prebuild).
 *
 * @param {string} contentDir
 * @returns {Array<{ id, term, definition, ... }>}
 */
export function getGlossaryTerms(contentDir) {
  if (!contentDir) return []
  const jsonlPath = path.join(contentDir, 'glossary', 'glossary-terms.jsonl')
  try {
    if (!fs.existsSync(jsonlPath)) return []
    const raw = fs.readFileSync(jsonlPath, 'utf8')
    return raw
      .trim()
      .split('\n')
      .filter(Boolean)
      .map(line => {
        try {
          return JSON.parse(line)
        } catch {
          return null
        }
      })
      .filter(Boolean)
  } catch {
    return []
  }
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/**
 * Returns all pages from the content directory, sectioned and sorted.
 *
 * Sort order within each section:
 *   1. Shallower URL paths first (index / overview pages)
 *   2. Alphabetical
 *
 * @returns {{
 *   bySection: Record<string, Array>,
 *   all: Array,
 *   contentDir: string|null
 * }}
 */
export function getAllPages() {
  const contentDir = findContentDir()
  if (!contentDir) return { bySection: {}, all: [], contentDir: null }

  const mdxFiles = getMdxFiles(contentDir)
  const bySection = Object.fromEntries(SECTION_ORDER.map(s => [s, []]))
  const all = []

  for (const filePath of mdxFiles) {
    const page = loadPage(filePath, contentDir)
    if (!page) continue
    // Skip the root landing page (index.mdx -> urlPath '') — it's a redirect
    // page with no standalone content useful for LLM ingestion.
    if (page.urlPath === '') continue
    const sec = page.section
    if (!bySection[sec]) bySection[sec] = []
    bySection[sec].push(page)
    all.push(page)
  }

  // Supplement glossary with any terms not yet generated as MDX files
  const glossaryTerms = getGlossaryTerms(contentDir)
  const existingGlossary = new Set((bySection.glossary || []).map(p => p.urlPath))
  for (const term of glossaryTerms) {
    const urlPath = `glossary/${term.id}`
    if (!existingGlossary.has(urlPath)) {
      const synth = {
        urlPath,
        title: term.term || humanizeSlug(term.id),
        description: term.definition || null,
        section: 'glossary',
        rawSource: null,
      }
      bySection.glossary.push(synth)
      all.push(synth)
    }
  }

  // Sort each section
  for (const sec of SECTION_ORDER) {
    bySection[sec].sort((a, b) => {
      const aDepth = (a.urlPath.match(/\//g) || []).length
      const bDepth = (b.urlPath.match(/\//g) || []).length
      if (aDepth !== bDepth) return aDepth - bDepth
      return a.urlPath.localeCompare(b.urlPath)
    })
  }

  return { bySection, all, contentDir }
}
