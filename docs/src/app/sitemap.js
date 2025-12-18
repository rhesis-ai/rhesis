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

export default async function sitemap() {
  const baseUrl = 'https://docs.rhesis.ai'
  const contentDir = path.join(__dirname, '../../content')

  // Get all MDX files from content directory
  const mdxFiles = getMdxFiles(contentDir)

  // Convert file paths to sitemap entries
  const sitemapEntries = mdxFiles.map(filePath => {
    const urlPath = filePathToUrl(filePath)
    const url = urlPath ? `${baseUrl}/${urlPath}` : baseUrl
    const priority = getPriority(urlPath)

    return {
      url,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority,
    }
  })

  // Sort by priority (highest first) and then by URL
  sitemapEntries.sort((a, b) => {
    if (b.priority !== a.priority) {
      return b.priority - a.priority
    }
    return a.url.localeCompare(b.url)
  })

  return sitemapEntries
}
