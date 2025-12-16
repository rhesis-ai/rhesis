import { Layout, Navbar } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import ThemeAwareLogo from '../components/ThemeAwareLogo'
import Footer from '../components/Footer'
import GitHubStarBanner from '../components/GitHubStarBanner'
import 'nextra-theme-docs/style.css'
import '../styles/globals.css'

export const metadata = {
  title: {
    template: '%s – Rhesis',
    default: 'Rhesis Documentation',
  },
  description: 'AI-powered testing and evaluation platform',
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
  },
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
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head />
      <body>
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
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
