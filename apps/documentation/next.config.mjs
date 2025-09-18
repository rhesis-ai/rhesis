import nextra from 'nextra'
 
// Nextra 4.x configuration
const withNextra = nextra({
  defaultShowCopyCode: true
})
 
// Export the final Next.js config with Nextra included
export default withNextra({
  // Add regular Next.js options here
  experimental: {
    appDir: true
  }
})