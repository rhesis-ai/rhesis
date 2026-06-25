/**
 * Generates the XML sitemap for docs.rhesis.ai.
 *
 * Uses the shared content scanner from lib/content-index.js so that
 * the sitemap stays in sync with llms.txt and llms-full.txt automatically.
 */

import fs from 'fs'
import path from 'path'
import {
  findContentDir,
  getMdxFiles,
  filePathToUrl,
  getGlossaryTerms,
} from '../lib/content-index.js'

const BASE_URL = 'https://docs.rhesis.ai'

/**
 * Priority by URL depth:
 *   root (0 segments)  → 1.0
 *   one segment        → 0.8
 *   two+ segments      → 0.6
 */
function getPriority(urlPath) {
  if (!urlPath) return 1.0
  const segments = urlPath.split('/').filter(Boolean)
  return segments.length === 1 ? 0.8 : 0.6
}

export default async function sitemap() {
  const contentDir = findContentDir()
  const urlSet = new Set()
  const entries = []

  const addEntry = (urlPath, lastModified = new Date()) => {
    const url = urlPath ? `${BASE_URL}/${urlPath}` : BASE_URL
    if (urlSet.has(url)) return
    urlSet.add(url)
    entries.push({
      url,
      lastModified,
      changeFrequency: 'weekly',
      priority: getPriority(urlPath),
    })
  }

  if (!contentDir) {
    // Minimal fallback when content dir is unavailable (e.g. partial build)
    // eslint-disable-next-line no-console
    console.warn('Content directory not found; sitemap will include base URL only')
    addEntry('')
  } else {
    for (const filePath of getMdxFiles(contentDir)) {
      const urlPath = filePathToUrl(filePath)
      let lastModified = new Date()
      try {
        lastModified = fs.statSync(path.join(contentDir, filePath)).mtime
      } catch {
        // use default lastModified
      }
      addEntry(urlPath, lastModified)
    }

    // Safety net: ensure glossary terms from the JSONL are always included
    // even if the generated MDX files haven't been built yet.
    for (const term of getGlossaryTerms(contentDir)) {
      addEntry(`glossary/${term.id}`)
    }
  }

  // Sort: highest priority first, then alphabetically
  entries.sort((a, b) => {
    if (b.priority !== a.priority) return b.priority - a.priority
    return a.url.localeCompare(b.url)
  })

  return entries
}
