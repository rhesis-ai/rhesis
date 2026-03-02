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
  }
}
