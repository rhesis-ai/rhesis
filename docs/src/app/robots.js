export default function robots() {
  const baseUrl = 'https://docs.rhesis.ai'

  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  }
}
