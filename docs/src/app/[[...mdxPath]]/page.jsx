import { generateStaticParamsFor, importPage } from 'nextra/pages'
import { notFound } from 'next/navigation'
import { useMDXComponents as getMDXComponents } from '../../mdx-components'
import { generatePageMetadata } from '../../lib/metadata'
import { siteConfig } from '../../lib/site-config'

export const generateStaticParams = generateStaticParamsFor('mdxPath')

export async function generateMetadata(props) {
  const params = await props.params

  try {
    const { metadata, sourceCode } = await importPage(params.mdxPath)

    // Construct URL path from mdxPath array
    const urlPath = params.mdxPath ? params.mdxPath.join('/') : ''

    // Generate enhanced metadata with SEO optimizations, passing sourceCode for description extraction
    const enhancedMetadata = generatePageMetadata(metadata, urlPath, siteConfig, sourceCode)

    return enhancedMetadata
  } catch (error) {
    // For actual MDX pages that don't exist, trigger Next.js 404
    notFound()
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
    // For actual MDX pages that don't exist, trigger Next.js 404
    notFound()
  }
}
