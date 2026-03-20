import nextra from 'nextra'
import path from 'path'
import { fileURLToPath } from 'url'
import { remarkMermaid } from '@theguild/remark-mermaid'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const withNextra = nextra({
  mdxOptions: {
    remarkPlugins: [remarkMermaid],
  },
})

export default withNextra({
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '../..'),
  async redirects() {
    const permanent = true
    return [
      { source: '/docs', destination: '/docs/getting-started', permanent },
      {
        source: '/penelope',
        destination: '/docs/conversation-simulation',
        permanent,
      },
      {
        source: '/penelope/:path*',
        destination: '/docs/conversation-simulation/:path*',
        permanent,
      },
      { source: '/getting-started', destination: '/docs/getting-started', permanent },
      {
        source: '/getting-started/:path*',
        destination: '/docs/getting-started/:path*',
        permanent,
      },
      { source: '/concepts', destination: '/docs/concepts', permanent },
      { source: '/product-tour', destination: '/docs/product-tour', permanent },
      { source: '/frameworks', destination: '/docs/frameworks', permanent },
      { source: '/acknowledgments', destination: '/docs/acknowledgments', permanent },
      { source: '/deployment', destination: '/docs/deployment', permanent },
      {
        source: '/deployment/:path*',
        destination: '/docs/deployment/:path*',
        permanent,
      },
      { source: '/tracing', destination: '/docs/tracing', permanent },
      { source: '/tracing/:path*', destination: '/docs/tracing/:path*', permanent },
      {
        source: '/conversation-simulation',
        destination: '/docs/conversation-simulation',
        permanent,
      },
      {
        source: '/conversation-simulation/:path*',
        destination: '/docs/conversation-simulation/:path*',
        permanent,
      },
      {
        source: '/adversarial-testing',
        destination: '/docs/adversarial-testing',
        permanent,
      },
      {
        source: '/adversarial-testing/:path*',
        destination: '/docs/adversarial-testing/:path*',
        permanent,
      },
      {
        source: '/multimodal-testing',
        destination: '/docs/multimodal-testing',
        permanent,
      },
      {
        source: '/multimodal-testing/:path*',
        destination: '/docs/multimodal-testing/:path*',
        permanent,
      },
      { source: '/platform', destination: '/docs/getting-started', permanent },
      {
        source: '/docs/projects/:path*',
        destination: '/docs/projects/:path*',
        permanent,
      },
      {
        source: '/docs/knowledge/:path*',
        destination: '/docs/knowledge/:path*',
        permanent,
      },
      {
        source: '/docs/behaviors/:path*',
        destination: '/docs/behaviors/:path*',
        permanent,
      },
      {
        source: '/docs/metrics/:path*',
        destination: '/docs/metrics/:path*',
        permanent,
      },
      {
        source: '/docs/tests-generation/:path*',
        destination: '/docs/tests-generation/:path*',
        permanent,
      },
      {
        source: '/docs/playground/:path*',
        destination: '/docs/playground/:path*',
        permanent,
      },
      {
        source: '/docs/tests/:path*',
        destination: '/docs/tests/:path*',
        permanent,
      },
      {
        source: '/docs/test-sets/:path*',
        destination: '/docs/test-sets/:path*',
        permanent,
      },
      {
        source: '/docs/test-execution/:path*',
        destination: '/docs/test-execution/:path*',
        permanent,
      },
      {
        source: '/docs/results-overview/:path*',
        destination: '/docs/results-overview/:path*',
        permanent,
      },
      {
        source: '/docs/test-runs/:path*',
        destination: '/docs/test-runs/:path*',
        permanent,
      },
      {
        source: '/docs/test-reviews/:path*',
        destination: '/docs/test-reviews/:path*',
        permanent,
      },
      {
        source: '/docs/tasks/:path*',
        destination: '/docs/tasks/:path*',
        permanent,
      },
      {
        source: '/docs/endpoints/:path*',
        destination: '/docs/endpoints/:path*',
        permanent,
      },
      {
        source: '/docs/models/:path*',
        destination: '/docs/models/:path*',
        permanent,
      },
      {
        source: '/docs/mcp/:path*',
        destination: '/docs/mcp/:path*',
        permanent,
      },
      {
        source: '/docs/api-tokens/:path*',
        destination: '/docs/api-tokens/:path*',
        permanent,
      },
      {
        source: '/docs/organizations/:path*',
        destination: '/docs/organizations/:path*',
        permanent,
      },
      {
        source: '/docs/integrations/:path*',
        destination: '/docs/integrations/:path*',
        permanent,
      },
      {
        source: '/docs/test-results/:path*',
        destination: '/docs/test-results/:path*',
        permanent,
      },
      {
        source: '/docs/test-sets-runs/:path*',
        destination: '/docs/test-sets-runs/:path*',
        permanent,
      },
      {
        source: '/docs/:path*',
        destination: '/docs/:path*',
        permanent,
      },
      { source: '/contributing', destination: '/contribute', permanent },
      { source: '/contribute/changelog', destination: '/changelog', permanent },
      {
        source: '/contribute/contributing/development-setup',
        destination: '/contribute/development-setup',
        permanent,
      },
      {
        source: '/contribute/contributing/development-setup/:path*',
        destination: '/contribute/development-setup/:path*',
        permanent,
      },
      {
        source: '/contribute/contributing/coding-standards',
        destination: '/contribute/coding-standards',
        permanent,
      },
      {
        source: '/contribute/contributing/coding-standards/:path*',
        destination: '/contribute/coding-standards/:path*',
        permanent,
      },
      {
        source: '/contribute/contributing/managing-docs',
        destination: '/contribute/managing-docs',
        permanent,
      },
      {
        source: '/contribute/contributing/managing-docs/:path*',
        destination: '/contribute/managing-docs/:path*',
        permanent,
      },
      {
        source: '/contribute/contributing',
        destination: '/contribute',
        permanent,
      },
      {
        source: '/contribute/contributing/:path*',
        destination: '/contribute/:path*',
        permanent,
      },
      { source: '/development', destination: '/contribute', permanent },
      {
        source: '/contribute/:path*',
        destination: '/contribute/:path*',
        permanent,
      },
    ]
  },
  webpack: config => {
    config.resolve.alias['@'] = path.resolve(__dirname)

    // Override @theguild/remark-mermaid/mermaid to use OUR custom wrapper
    // This ensures our theme-aware Mermaid component is used instead of the default
    const ourMermaidPath = path.resolve(__dirname, 'components/MermaidWrapper.jsx')
    config.resolve.alias['@theguild/remark-mermaid/mermaid'] = ourMermaidPath

    // Add support for .jsonl files (JSONL - JSON Lines format)
    config.module.rules.push({
      test: /\.jsonl$/,
      type: 'asset/source',
    })

    return config
  },
})
