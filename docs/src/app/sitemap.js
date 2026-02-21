import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

/**
 * Recursively scans a directory for .mdx files and returns their paths
 * @param {string} dir - Directory to scan
 * @param {string} baseDir - Base directory for calculating relative paths
 * @returns {string[]} - Array of relative file paths
 */
function getMdxFiles(dir, baseDir = dir) {
  const files = []
  const items = fs.readdirSync(dir, { withFileTypes: true })

  for (const item of items) {
    const fullPath = path.join(dir, item.name)

    if (item.isDirectory()) {
      // Skip node_modules and hidden directories
      if (!item.name.startsWith('.') && item.name !== 'node_modules') {
        files.push(...getMdxFiles(fullPath, baseDir))
      }
    } else if (item.isFile() && item.name.endsWith('.mdx')) {
      // Skip _meta files and other non-content files
      if (!item.name.startsWith('_')) {
        const relativePath = path.relative(baseDir, fullPath)
        files.push(relativePath)
      }
    }
  }

  return files
}

/**
 * Converts a file path to a URL path following Nextra conventions
 * @param {string} filePath - Relative file path
 * @returns {string} - URL path
 */
function filePathToUrl(filePath) {
  // Remove .mdx extension
  let urlPath = filePath.replace(/\.mdx$/, '')

  // Convert backslashes to forward slashes (Windows compatibility)
  urlPath = urlPath.replace(/\\/g, '/')

  // Handle index files - they map to the directory URL
  urlPath = urlPath.replace(/\/index$/, '')

  // If the result is empty (root index), return '/'
  if (!urlPath || urlPath === 'index') {
    return ''
  }

  return urlPath
}

/**
 * Determines priority based on URL structure
 * @param {string} url - URL path
 * @returns {number} - Priority value (0.0 to 1.0)
 */
function getPriority(url) {
  // Root page
  if (url === '') {
    return 1.0
  }

  // Section index pages (one level deep, no trailing segments)
  const segments = url.split('/').filter(Boolean)
  if (segments.length === 1) {
    return 0.8
  }

  // All other pages
  return 0.6
}

/**
 * Loads glossary term IDs from glossary-terms.jsonl so the sitemap includes every term.
 * Terms are generated at build time (prebuild) into content/glossary/<id>/index.mdx; this
 * ensures the sitemap stays complete if the content tree is partial (e.g. build context).
 * @param {string[]} possibleContentDirs - Directories that might contain content
 * @returns {string[]} - Term IDs (URL slugs) for glossary pages
 */
function getGlossaryTermIds(possibleContentDirs) {
  const jsonlPath = path.join('glossary', 'glossary-terms.jsonl')
  for (const dir of possibleContentDirs) {
    const fullPath = path.join(dir, jsonlPath)
    try {
      if (fs.existsSync(fullPath)) {
        const raw = fs.readFileSync(fullPath, 'utf8')
        return raw
          .trim()
          .split('\n')
          .filter(Boolean)
          .map(line => {
            const row = JSON.parse(line)
            return row?.id
          })
          .filter(Boolean)
      }
    } catch {
      // Continue to next directory
    }
  }
  return []
}

export default async function sitemap() {
  const baseUrl = 'https://docs.rhesis.ai'

  // Try multiple possible content directory locations
  const possibleContentDirs = [
    path.join(__dirname, '../../content'), // Local development
    path.join(process.cwd(), 'content'), // Docker/production
    path.join(__dirname, '../../../content'), // Alternative structure
  ]

  let contentDir = null
  for (const dir of possibleContentDirs) {
    try {
      if (fs.existsSync(dir)) {
        contentDir = dir
        break
      }
    } catch (error) {
      // Continue to next option
    }
  }

  const urlSet = new Set()
  const sitemapEntries = []

  if (!contentDir) {
    // eslint-disable-next-line no-console
    console.warn('Content directory not found, generating minimal sitemap')
    sitemapEntries.push({
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1.0,
    })
    urlSet.add(baseUrl)
  } else {
    // Get all MDX files from content directory
    const mdxFiles = getMdxFiles(contentDir)

    for (const filePath of mdxFiles) {
      const urlPath = filePathToUrl(filePath)
      const url = urlPath ? `${baseUrl}/${urlPath}` : baseUrl
      if (urlSet.has(url)) continue
      urlSet.add(url)
      sitemapEntries.push({
        url,
        lastModified: new Date(),
        changeFrequency: 'weekly',
        priority: getPriority(urlPath),
      })
    }
  }

  // Ensure every glossary term from glossary-terms.jsonl is in the sitemap
  // (safety net if any generated term dirs were missing from the content copy).
  const glossaryTermIds = getGlossaryTermIds(possibleContentDirs)
  const glossaryPriority = 0.6
  for (const termId of glossaryTermIds) {
    const url = `${baseUrl}/glossary/${termId}`
    if (urlSet.has(url)) continue
    urlSet.add(url)
    sitemapEntries.push({
      url,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: glossaryPriority,
    })
  }

  // Sort by priority (highest first) and then by URL
  sitemapEntries.sort((a, b) => {
    if (b.priority !== a.priority) {
      return b.priority - a.priority
    }
    return a.url.localeCompare(b.url)
  })

  return sitemapEntries
}
