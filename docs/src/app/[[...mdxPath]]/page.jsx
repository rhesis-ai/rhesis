import { generateStaticParamsFor, importPage } from 'nextra/pages'
import { useMDXComponents as getMDXComponents } from '../../mdx-components'
import { generatePageMetadata } from '../../lib/metadata'
import { siteConfig } from '../../lib/site-config'

export const generateStaticParams = generateStaticParamsFor('mdxPath')

export async function generateMetadata(props) {
  const params = await props.params

  try {
    const { metadata } = await importPage(params.mdxPath)

    // Construct URL path from mdxPath array
    const urlPath = params.mdxPath ? params.mdxPath.join('/') : ''

    // Generate enhanced metadata with SEO optimizations
    const enhancedMetadata = generatePageMetadata(metadata, urlPath, siteConfig)

    return enhancedMetadata
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('Failed to load metadata for path:', params.mdxPath, error)

    // Fallback metadata with basic SEO
    const urlPath = params.mdxPath ? params.mdxPath.join('/') : ''
    return generatePageMetadata(
      {
        title: 'Rhesis Documentation',
        description: siteConfig.siteDescription,
      },
      urlPath,
      siteConfig
    )
  }
}

const Wrapper = getMDXComponents().wrapper

export default async function Page(props) {
  const params = await props.params

  try {
    const { default: MDXContent, toc, metadata, sourceCode } = await importPage(params.mdxPath)
    return (
      <Wrapper toc={toc} metadata={metadata} sourceCode={sourceCode}>
        <MDXContent {...props} params={params} />
      </Wrapper>
    )
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('Failed to load page for path:', params.mdxPath, error)
    return (
      <Wrapper toc={[]} metadata={{ title: 'Page Not Found' }} sourceCode="">
        <div>
          <h1>Page Not Found</h1>
          <p>The requested page could not be found.</p>
        </div>
      </Wrapper>
    )
  }
}
