import { useMDXComponents as getThemeComponents } from 'nextra-theme-docs'
import { Callout } from 'nextra/components'

// Get the default MDX components
const themeComponents = getThemeComponents()

// Merge components
export function useMDXComponents(components) {
  return {
    ...themeComponents,
    ...components,
    // Add the Callout component for Nextra 4
    Callout,
  }
}