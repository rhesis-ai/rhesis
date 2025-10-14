import nextra from 'nextra'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const withNextra = nextra({})

export default withNextra({
  outputFileTracingRoot: path.join(__dirname, '../..'),
  webpack: config => {
    config.resolve.alias['@'] = path.resolve(__dirname)
    return config
  },
})
