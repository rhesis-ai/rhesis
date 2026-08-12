/**
 * Resolves a docs URL path to the text that goes on its social card.
 *
 * Kept out of the route handler so it can be unit-tested without a Next.js
 * runtime, the same way `llm-views.js` backs `/api/md`. Titles come from the
 * same scanner as the sitemap and llms.txt, so a renamed heading updates the
 * card without anyone touching frontmatter.
 */

import path from 'path'

import { findContentDir, urlToFilePath, loadPage, SECTION_LABELS } from './content-index.js'
import { siteConfig } from './site-config.js'
import { stripBrandSuffix } from './og-theme.js'

/**
 * @param {string} urlPath - URL path without leading slash, e.g. "docs/concepts"
 * @returns {{ title: string, description: string, section: string, found: boolean }}
 */
export function resolveOgPage(urlPath) {
  const fallback = {
    title: siteConfig.siteName,
    description: siteConfig.siteDescription,
    section: SECTION_LABELS.docs,
    found: false,
  }

  const cleanPath = (urlPath || '').replace(/^\/+|\/+$/g, '')
  const contentDir = findContentDir()
  if (!contentDir) return fallback

  const filePath = urlToFilePath(cleanPath, contentDir)
  if (!filePath) return fallback

  const page = loadPage(path.relative(contentDir, filePath), contentDir)
  if (!page) return fallback

  return {
    title: page.title ? stripBrandSuffix(page.title) : fallback.title,
    description: page.description || siteConfig.siteDescription,
    section: SECTION_LABELS[page.section] || SECTION_LABELS.docs,
    found: true,
  }
}
