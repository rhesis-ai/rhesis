export const dynamic = 'force-dynamic'

export default function robots() {
  const baseUrl = 'https://docs.rhesis.ai'
  const isNoIndex = process.env.ROBOTS_NOINDEX === 'true'

  if (isNoIndex) {
    return {
      rules: {
        userAgent: '*',
        disallow: '/',
      },
    }
  }

  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
    // LLM-consumable files (llmstxt.org)
    // llmsTxt: `${baseUrl}/llms.txt`,  (not a standard robots.txt directive yet)
  }
}
