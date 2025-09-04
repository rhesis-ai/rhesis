import nextra from 'nextra'
 
// Set up Nextra with its configuration
const withNextra = nextra({
  defaultShowCopyCode: true,
  staticImage: true,
  mdxOptions: {
    remarkPlugins: [],
    rehypePlugins: []
  }
})
 
// Export the final Next.js config with Nextra included
export default withNextra({
  // Add regular Next.js options here
  experimental: {
    mdxRs: true
  }
})