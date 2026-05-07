import { NextResponse } from 'next/server'

export function middleware(request) {
  const { pathname } = request.nextUrl

  // Rewrite /<page>.md requests to the internal markdown API route.
  // This powers the "any page as raw markdown" feature: append .md to any
  // docs URL to get clean markdown suitable for LLM ingestion.
  if (
    pathname.endsWith('.md') &&
    pathname.length > 3 &&
    !pathname.startsWith('/api/') &&
    !pathname.startsWith('/_next/')
  ) {
    const slug = pathname.slice(1, -3) // strip leading "/" and trailing ".md"
    const url = request.nextUrl.clone()
    url.pathname = `/api/md/${slug}`
    return NextResponse.rewrite(url)
  }

  // List of paths that should NOT be handled by the MDX catch-all route
  const staticPaths = [
    '/_next',
    '/api',
    '/favicon.ico',
    '/robots.txt',
    '/sitemap.xml',
    '/llms.txt',
    '/llms-full.txt',
    '/manifest.json',
    '/_vercel',
    '/public',
  ]

  // Check if the request is for a static resource
  const isStaticPath = staticPaths.some(path => pathname.startsWith(path))

  // Check if the request is for a file with a common static extension
  const staticExtensions = [
    '.ico',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.svg',
    '.webp',
    '.woff',
    '.woff2',
    '.ttf',
    '.eot',
    '.css',
    '.js',
    '.json',
  ]
  const hasStaticExtension = staticExtensions.some(ext => pathname.endsWith(ext))

  // If it's a static resource, let Next.js handle it naturally (skip the catch-all)
  if (isStaticPath || hasStaticExtension) {
    return NextResponse.next()
  }

  // For all other paths, continue to the catch-all MDX route
  return NextResponse.next()
}

export const config = {
  // Match all paths except those that are explicitly static
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - manifest.json (web app manifest)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|manifest.json).*)',
  ],
}
