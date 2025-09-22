import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import { Banner, Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import ThemeAwareLogo from '../components/ThemeAwareLogo'
import 'nextra-theme-docs/style.css'
import '../styles/globals.css'

export const metadata = {
  title: {
    template: '%s – Rhesis',
    default: 'Rhesis Documentation'
  },
  description: 'AI-powered testing and evaluation platform',
  icons: {
    icon: [
      {
        url: '/Rhesis AI_Logo_RGB_Favicon.svg',
        type: 'image/svg+xml',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/Rhesis AI_Logo_RGB_Favicon_white.svg',
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

const footer = (
  <Footer>
    © 2025 Rhesis AI GmbH. Made in Germany.
  </Footer>
)

export default async function RootLayout({ children }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head />
      <body>
        <Layout 
          navbar={navbar}
          footer={footer}
          pageMap={await getPageMap()}
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
