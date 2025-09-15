import { Layout } from 'nextra-theme-docs'
import { getPageMap } from 'nextra/page-map'
import 'nextra-theme-docs/style.css'

export default async function RootLayout({ children }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <body>
        <Layout pageMap={await getPageMap()}>
          {children}
        </Layout>
      </body>
    </html>
  )
}
