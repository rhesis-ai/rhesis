import { generateStaticParamsFor, importPage } from 'nextra/pages'
import { useMDXComponents as getMDXComponents } from '../../mdx-components'

export const generateStaticParams = generateStaticParamsFor('mdxPath')

export async function generateMetadata(props) {
  const params = await props.params

  try {
    const { metadata } = await importPage(params.mdxPath)
    return metadata
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('Failed to load metadata for path:', params.mdxPath, error)
    return {
      title: 'Rhesis Documentation',
      description: 'AI-powered testing and evaluation platform',
    }
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
