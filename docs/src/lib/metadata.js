import { siteConfig } from './site-config.js'
import { OG_VERSION, cardKey, stripBrandSuffix } from './og-theme.js'

/**
 * Generates canonical URL for a given path
 * @param {string} path - The page path (e.g., 'getting-started' or '')
 * @param {object} config - Site configuration object
 * @returns {string} - Full canonical URL
 */
export function getCanonicalUrl(path, config = siteConfig) {
  const cleanPath = path ? `/${path}` : ''
  return `${config.siteUrl}${cleanPath}`
}

/**
 * Builds the OpenGraph image URL for a page.
 *
 * Every page gets its own card, rendered on demand by /api/og from the page's
 * own title and description. Both query parameters exist to defeat caching,
 * since crawlers and CDNs key social images by URL and nothing else: `v` is the
 * card design version, and `h` changes when this page's own text changes.
 *
 * Pages that want a hand-made image instead set `ogImage` in frontmatter; it
 * must be an absolute URL or a path under public/ (PNG or JPEG — LinkedIn and
 * Facebook do not render webp reliably).
 *
 * @param {string} path - The page path, e.g. 'docs/endpoints' ('' for the root)
 * @param {string|null} pageImage - Optional per-page override from frontmatter
 * @param {string|null} cardText - Text the card renders, hashed into `h`
 * @returns {string} - Full image URL
 */
export function getOpenGraphImage(path, pageImage = null, cardText = null) {
  if (pageImage) {
    return /^https?:\/\//.test(pageImage) ? pageImage : `${siteConfig.siteUrl}${pageImage}`
  }

  const cleanPath = (path || '').replace(/^\/+|\/+$/g, '')
  const params = new URLSearchParams()
  if (cleanPath) params.set('p', cleanPath)
  params.set('v', OG_VERSION)
  if (cardText) params.set('h', cardKey(cardText))

  return `${siteConfig.siteUrl}/api/og?${params}`
}

/**
 * Extracts a description from content if not provided in metadata
 * @param {string} content - Page content (MDX string)
 * @returns {string|null} - Extracted description or null
 */
export function extractDescription(content) {
  if (!content) return null

  // Remove YAML frontmatter block (--- ... ---)
  let cleanContent = content.replace(/^---\n[\s\S]*?\n---\n?/, '')

  // Remove MDX imports, exports, code blocks, inline code, and MDX components.
  // Multi-line exports go first: `export const metadata = {...}` (what the
  // generated glossary pages use) would otherwise leave its object body behind
  // and get picked up as the first paragraph.
  cleanContent = cleanContent
    .replace(/^export\s+(?:const|let|var)\s+\w+\s*=\s*\{[\s\S]*?^\}\s*$/gm, '')
    .replace(/^import\s+.*$/gm, '')
    .replace(/^export\s+.*$/gm, '')
    .replace(/```[\s\S]*?```/g, '')
    // Inline code keeps its text: dropping it would leave `**` + `**` around a
    // hole, and the emphasis unwrap below would then pair the wrong asterisks.
    .replace(/`([^`]+)`/g, '$1')
    .replace(/<[^>]+>/g, '')

  // Remove the first H1 heading (page title)
  cleanContent = cleanContent.replace(/^#\s+[^\n]+\n*/m, '')

  // Remove all remaining heading markers (##, ###, etc.) but keep the text
  cleanContent = cleanContent.replace(/^#+\s+/gm, '')

  // Unwrap inline markdown — descriptions are plain text, and a lead paragraph
  // wrapped in ** would otherwise ship the asterisks to search results and
  // social cards.
  cleanContent = cleanContent
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/(\*\*|__)(.+?)\1/g, '$2')
    .replace(/(^|[\s(])[*_]([^*_\n]+)[*_](?=[\s).,;:!?]|$)/g, '$1$2')

  // Clean up and normalize whitespace
  cleanContent = cleanContent.trim()

  // Split into paragraphs and find the first substantial one (at least 20 chars)
  const paragraphs = cleanContent.split(/\n\n+/).filter(p => p.trim().length >= 20)
  if (paragraphs.length === 0) return null

  // Take first paragraph and normalize line breaks to spaces
  const firstParagraph = paragraphs[0].replace(/\s+/g, ' ').trim()
  if (!firstParagraph) return null

  // Limit to ~160 characters for SEO
  const description = firstParagraph.substring(0, 160)

  return description.length < firstParagraph.length ? `${description}...` : description
}

/**
 * Generates comprehensive page metadata for SEO
 * @param {object} baseMetadata - Base metadata from Nextra/MDX
 * @param {string} urlPath - URL path for the page
 * @param {object} config - Site configuration
 * @param {string} sourceCode - Optional MDX source code for description extraction
 * @returns {object} - Enhanced metadata object for Next.js
 */
export function generatePageMetadata(
  baseMetadata,
  urlPath,
  config = siteConfig,
  sourceCode = null
) {
  const title = baseMetadata?.title || config.siteName

  // Try to get description from: 1) metadata, 2) extracted from content, 3) site default
  let description = baseMetadata?.description
  if (!description && sourceCode) {
    description = extractDescription(sourceCode)
  }
  if (!description) {
    description = config.siteDescription
  }

  // Merge page-level keywords (from frontmatter) with sitewide defaults
  const pageKeywords = baseMetadata?.keywords
  const keywords = pageKeywords
    ? [
        ...new Set([
          ...(Array.isArray(pageKeywords) ? pageKeywords : [pageKeywords]),
          ...config.keywords,
        ]),
      ]
    : config.keywords

  const canonicalUrl = getCanonicalUrl(urlPath, config)
  const imageUrl = getOpenGraphImage(urlPath, baseMetadata?.ogImage, `${title}${description}`)

  // Respect ROBOTS_NOINDEX env var (e.g. staging deployments)
  const noIndex = process.env.ROBOTS_NOINDEX === 'true'

  return {
    title,
    description,
    keywords,
    authors: [{ name: config.author.name, url: config.author.url }],
    creator: config.author.name,
    publisher: config.organization.name,

    // Canonical URL + raw markdown alternate (for LLM ingestion).
    // Skip the root page: appending ".md" to the bare site URL produces
    // "https://docs.rhesis.ai.md" which is not a valid URL and not a route
    // we serve. Site-wide /llms.txt and /llms-full.txt cover the root.
    alternates: {
      canonical: canonicalUrl,
      ...(urlPath
        ? {
            types: {
              'text/markdown': `${canonicalUrl}.md`,
            },
          }
        : {}),
    },

    // OpenGraph
    openGraph: {
      type: 'website',
      url: canonicalUrl,
      title,
      description,
      siteName: config.siteName,
      locale: config.locale,
      images: [
        {
          url: imageUrl,
          width: 1200,
          height: 630,
          alt: `${stripBrandSuffix(title)} – ${config.siteName}`,
        },
      ],
    },

    // Twitter Card
    twitter: {
      card: 'summary_large_image',
      site: config.twitterSite,
      creator: config.twitterHandle,
      title,
      description,
      images: [imageUrl],
    },

    // Robots — respect ROBOTS_NOINDEX for staging/preview environments
    robots: {
      index: !noIndex,
      follow: !noIndex,
      googleBot: {
        index: !noIndex,
        follow: !noIndex,
        'max-video-preview': -1,
        'max-image-preview': 'large',
        'max-snippet': -1,
      },
    },
  }
}

/**
 * Generates viewport configuration
 * @param {object} config - Site configuration
 * @returns {object} - Viewport configuration
 */
export function generateViewport(config = siteConfig) {
  return {
    themeColor: config.themeColor,
    width: 'device-width',
    initialScale: 1,
  }
}

/**
 * Generates JSON-LD structured data for the organization
 * @param {object} config - Site configuration
 * @returns {object} - JSON-LD structured data
 */
export function generateOrganizationSchema(config = siteConfig) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: config.organization.name,
    url: config.organization.url,
    logo: config.organization.logo,
    description: config.organization.description,
    sameAs: [
      'https://github.com/rhesis-ai/rhesis',
      'https://discord.rhesis.ai',
      'https://twitter.com/rhesis_ai',
    ],
  }
}

/**
 * Generates JSON-LD structured data for a website
 * @param {object} config - Site configuration
 * @returns {object} - JSON-LD structured data
 */
export function generateWebsiteSchema(config = siteConfig) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: config.siteName,
    url: config.siteUrl,
    description: config.siteDescription,
    publisher: {
      '@type': 'Organization',
      name: config.organization.name,
      logo: {
        '@type': 'ImageObject',
        url: config.organization.logo,
      },
    },
    inLanguage: config.language,
  }
}

/**
 * Generates JSON-LD structured data for a documentation page
 * @param {string} title - Page title
 * @param {string} description - Page description
 * @param {string} url - Page URL
 * @param {object} config - Site configuration
 * @returns {object} - JSON-LD structured data
 */
export function generateDocumentationSchema(title, description, url, config = siteConfig) {
  return {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    headline: title,
    description: description,
    url: url,
    publisher: {
      '@type': 'Organization',
      name: config.organization.name,
      logo: {
        '@type': 'ImageObject',
        url: config.organization.logo,
      },
    },
    inLanguage: config.language,
  }
}

/**
 * Generates JSON-LD structured data for a glossary term
 * @param {string} term - Term name
 * @param {string} definition - Term definition
 * @param {string} url - Term URL
 * @param {object} config - Site configuration
 * @returns {object} - JSON-LD structured data
 */
export function generateGlossaryTermSchema(term, definition, url, config = siteConfig) {
  return {
    '@context': 'https://schema.org',
    '@type': 'DefinedTerm',
    name: term,
    description: definition,
    url: url,
    inDefinedTermSet: {
      '@type': 'DefinedTermSet',
      name: 'Rhesis Platform Glossary',
      url: `${config.siteUrl}/glossary`,
    },
  }
}
