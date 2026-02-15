import { Layout, Navbar } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import ThemeAwareLogo from '../components/ThemeAwareLogo'
import Footer from '../components/Footer'
import GitHubStarBanner from '../components/GitHubStarBanner'
import { siteConfig } from '../lib/site-config'
import { generateOrganizationSchema, generateWebsiteSchema } from '../lib/metadata'
import 'nextra-theme-docs/style.css'
import '../styles/globals.css'

export const metadata = {
  metadataBase: new URL(siteConfig.siteUrl),
  title: {
    template: '%s – Rhesis',
    default: siteConfig.siteName,
  },
  description: siteConfig.siteDescription,
  keywords: siteConfig.keywords,
  authors: [{ name: siteConfig.author.name, url: siteConfig.author.url }],
  creator: siteConfig.author.name,
  publisher: siteConfig.organization.name,

  // Icons
  icons: {
    icon: [
      {
        url: '/logo/rhesis-logo-favicon.svg',
        type: 'image/svg+xml',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/logo/rhesis-logo-favicon-white.svg',
        type: 'image/svg+xml',
        media: '(prefers-color-scheme: dark)',
      },
    ],
    apple: '/logo/rhesis-logo-favicon.svg',
  },

  // Manifest
  manifest: '/manifest.json',

  // OpenGraph
  openGraph: {
    type: 'website',
    locale: siteConfig.locale,
    url: siteConfig.siteUrl,
    siteName: siteConfig.siteName,
    title: siteConfig.siteName,
    description: siteConfig.siteDescription,
    images: [
      {
        url: `${siteConfig.siteUrl}${siteConfig.defaultImage}`,
        width: 1200,
        height: 630,
        alt: siteConfig.defaultImageAlt,
      },
    ],
  },

  // Twitter
  twitter: {
    card: 'summary_large_image',
    site: siteConfig.twitterSite,
    creator: siteConfig.twitterHandle,
    title: siteConfig.siteName,
    description: siteConfig.siteDescription,
    images: [`${siteConfig.siteUrl}${siteConfig.defaultImage}`],
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

  // Verification (add when needed)
  // verification: {
  //   google: 'google-site-verification-code',
  // },
}

export const viewport = {
  themeColor: siteConfig.themeColor,
  width: 'device-width',
  initialScale: 1,
}

const navbar = (
  <Navbar
    logo={<ThemeAwareLogo />}
    projectLink="https://github.com/rhesis-ai/rhesis"
    chatLink="https://discord.rhesis.ai"
  />
)

const footer = <Footer />

export default async function RootLayout({ children }) {
  const organizationSchema = generateOrganizationSchema()
  const websiteSchema = generateWebsiteSchema()

  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head />
      <body>
        {/* Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
        />
        <GitHubStarBanner />
        <Layout
          navbar={navbar}
          footer={footer}
          pageMap={await getPageMap()}
          sidebar={{
            defaultMenuCollapseLevel: 1,
            autoCollapse: true,
            toggleButton: true,
          }}
          editLink={null}
          feedback={{
            content: 'Questions, feedbacks? Contact us!',
            labels: 'feedback',
            link: 'https://www.rhesis.ai/talk-to-us',
          }}
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
