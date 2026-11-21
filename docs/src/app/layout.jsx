import { Layout, Navbar } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import NavLogo from '../components/NavLogo'
import GradientBackdrop from '../components/GradientBackdrop'
import Footer from '../components/Footer'
import ThemeA11yFixes from '../components/ThemeA11yFixes'
import CollapsibleSidebar from '../components/CollapsibleSidebar'
import { siteConfig } from '../lib/site-config'
import {
  generateOrganizationSchema,
  generateWebsiteSchema,
  getOpenGraphImage,
} from '../lib/metadata'
import 'nextra-theme-docs/style.css'
import '../styles/globals.css'

export async function generateMetadata() {
  const isNoIndex = process.env.ROBOTS_NOINDEX === 'true'
  // Root-level default; per-page cards come from generatePageMetadata.
  const imageUrl = getOpenGraphImage('')

  return {
    metadataBase: new URL(siteConfig.siteUrl),
    title: {
      template: '%s – Rhesis',
      default: siteConfig.siteName,
    },
    // LLM-consumable corpus files (llmstxt.org)
    alternates: {
      types: {
        'text/plain': [
          { url: '/llms.txt', title: 'LLM index (llms.txt)' },
          { url: '/llms-full.txt', title: 'Full documentation corpus (llms-full.txt)' },
        ],
      },
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
          url: imageUrl,
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
      images: [imageUrl],
    },

    // Robots
    robots: isNoIndex
      ? {
          index: false,
          follow: false,
          googleBot: { index: false, follow: false },
        }
      : {
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
}

export const viewport = {
  themeColor: siteConfig.themeColor,
  width: 'device-width',
  initialScale: 1,
}

// Nextra names the logo link "Home page" and leaves the chat icon unnamed, so
// both get their own accessible names here (WCAG 2.5.3, 4.1.2).
const navbar = (
  <Navbar
    logo={
      <a href="/" className="rhesis-navlogo-link">
        <NavLogo />
      </a>
    }
    logoLink={false}
    projectLink="https://github.com/rhesis-ai/rhesis"
    chatLink="https://discord.rhesis.ai"
    chatIcon={
      <svg role="img" aria-label="Discord" fill="currentColor" viewBox="0 0 16 16" width="22">
        <path d="M13.545 2.907a13.2 13.2 0 0 0-3.257-1.011.05.05 0 0 0-.052.025c-.141.25-.297.577-.406.833a12.2 12.2 0 0 0-3.658 0 8 8 0 0 0-.412-.833.05.05 0 0 0-.052-.025c-1.125.194-2.22.534-3.257 1.011a.04.04 0 0 0-.021.018C.356 6.024-.213 9.047.066 12.032q.003.022.021.037a13.3 13.3 0 0 0 3.995 2.02.05.05 0 0 0 .056-.019q.463-.63.818-1.329a.05.05 0 0 0-.01-.059l-.018-.011a9 9 0 0 1-1.248-.595.05.05 0 0 1-.02-.066l.015-.019q.127-.095.248-.195a.05.05 0 0 1 .051-.007c2.619 1.196 5.454 1.196 8.041 0a.05.05 0 0 1 .053.007q.121.1.248.195a.05.05 0 0 1-.004.085 8 8 0 0 1-1.249.594.05.05 0 0 0-.03.03.05.05 0 0 0 .003.041c.24.465.515.909.817 1.329a.05.05 0 0 0 .056.019 13.2 13.2 0 0 0 4.001-2.02.05.05 0 0 0 .021-.037c.334-3.451-.559-6.449-2.366-9.106a.03.03 0 0 0-.02-.019m-8.198 7.307c-.789 0-1.438-.724-1.438-1.612s.637-1.613 1.438-1.613c.807 0 1.45.73 1.438 1.613 0 .888-.637 1.612-1.438 1.612m5.316 0c-.788 0-1.438-.724-1.438-1.612s.637-1.613 1.438-1.613c.807 0 1.451.73 1.438 1.613 0 .888-.631 1.612-1.438 1.612" />
      </svg>
    }
  />
)

const footer = <Footer />

export default async function RootLayout({ children }) {
  const organizationSchema = generateOrganizationSchema()
  const websiteSchema = generateWebsiteSchema()

  const pageMap = await getPageMap()

  // Behind a build-time flag. The import sits inside the check so a build without the flag
  // doesn't load the widget at all.
  const AskDocs =
    process.env.NEXT_PUBLIC_ASK_DOCS === '1'
      ? (await import('../components/AskDocs/AskDocs')).default
      : null

  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      {/*
        Nextra's accent colour and page background. `Head` emits these as an
        inline <style>, so it beats any stylesheet — configuring them here is the
        only thing that actually takes effect, and it survives Nextra upgrades in
        a way that overriding the generated `x:bg-primary-*` classes would not.

        Nextra derives its whole primary ramp from these HSL values: the active
        sidebar link is `bg-primary-100` (lightness + 49%) with
        `text-primary-800` (lightness - 13%). Desaturating to a cool grey is the
        "neutral primary" case the Nextra docs call out, and it is what takes the
        chrome off the old tinted-blue selection. Dark lightness of 100 clamps the
        ramp to white, so the selected row lands on white @ 10%.
      */}
      <Head
        color={{
          hue: 220,
          saturation: { light: 15, dark: 0 },
          lightness: { light: 42, dark: 100 },
        }}
        backgroundColor={{ light: '#ffffff', dark: '#030712' }}
      />
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
        <GradientBackdrop />
        <CollapsibleSidebar />
        <Layout
          navbar={navbar}
          footer={footer}
          pageMap={pageMap}
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
        <ThemeA11yFixes />
        {AskDocs && <AskDocs />}
      </body>
    </html>
  )
}
