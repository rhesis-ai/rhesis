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
  outputFileTracingRoot: path.join(__dirname, '../..'),
  webpack: config => {
    config.resolve.alias['@'] = path.resolve(__dirname)

    // Resolve @theguild/remark-mermaid/mermaid to the actual file
    // The package uses wildcard exports (./*) which may not resolve correctly in all contexts
    const mermaidPath = path.resolve(
      __dirname,
      'node_modules/@theguild/remark-mermaid/dist/mermaid.js'
    )
    config.resolve.alias['@theguild/remark-mermaid/mermaid'] = mermaidPath

    return config
  },
})
