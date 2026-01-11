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
