import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import { Banner, Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import ThemeAwareLogo from '../components/ThemeAwareLogo'
import 'nextra-theme-docs/style.css'

export const metadata = {
  title: {
    template: '%s – Rhesis',
    default: 'Rhesis Documentation'
  },
  description: 'AI-powered testing and evaluation platform',
}

const banner = (
  <Banner storageKey="rhesis-docs">
    Welcome to Rhesis Documentation 🚀
  </Banner>
)

const navbar = (
  <Navbar
    logo={<ThemeAwareLogo />}
    projectLink="https://github.com/rhesis-ai/rhesis"
    chatLink="https://discord.rhesis.ai"
  />
)

const footer = (
  <Footer>
    © 2025 Rhesis AI GmbH. Made in Germany.
  </Footer>
)

export default async function RootLayout({ children }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <meta property="og:title" content="Rhesis Documentation" />
        <meta property="og:description" content="AI-powered testing and evaluation platform" />
        <link rel="icon" type="image/svg+xml" href="/Rhesis AI_Logo_RGB_Favicon_white.svg" />
      </Head>
      <body>
        <Layout
          banner={banner}
          navbar={navbar}
          pageMap={await getPageMap()}
          docsRepositoryBase="https://github.com/rhesis-ai/rhesis"
          footer={footer}
          sidebar={{
            defaultMenuCollapseLevel: 1,
            autoCollapse: true,
            toggleButton: true
          }}
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
