import { siteConfig } from './site-config'

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
 * Generates OpenGraph image URL
 * @param {string} path - The page path
 * @param {string} defaultImage - Default image path from config
 * @returns {string} - Full image URL
 */
export function getOpenGraphImage(path, defaultImage = siteConfig.defaultImage) {
  // In the future, we could check for page-specific images
  // For now, return the default image with full URL
  return `${siteConfig.siteUrl}${defaultImage}`
}

/**
 * Extracts a description from content if not provided in metadata
 * @param {string} content - Page content (MDX string)
 * @returns {string|null} - Extracted description or null
 */
export function extractDescription(content) {
  if (!content) return null

  // Remove MDX imports and components
  const cleanContent = content
    .replace(/^import\s+.*$/gm, '')
    .replace(/<[^>]+>/g, '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`[^`]+`/g, '')
    .replace(/#+\s+/g, '')
    .trim()

  // Get first paragraph (up to first double newline or 160 chars)
  const firstParagraph = cleanContent.split('\n\n')[0]
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
 * @returns {object} - Enhanced metadata object for Next.js
 */
export function generatePageMetadata(baseMetadata, urlPath, config = siteConfig) {
  const title = baseMetadata?.title || config.siteName
  const description = baseMetadata?.description || config.siteDescription
  const canonicalUrl = getCanonicalUrl(urlPath, config)
  const imageUrl = getOpenGraphImage(urlPath, config.defaultImage)

  return {
    title,
    description,
    keywords: config.keywords,
    authors: [{ name: config.author.name, url: config.author.url }],
    creator: config.author.name,
    publisher: config.organization.name,

    // Canonical URL
    alternates: {
      canonical: canonicalUrl,
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
          alt: config.defaultImageAlt,
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

    // Robots
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
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
