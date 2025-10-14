import { useMDXComponents as getThemeComponents } from 'nextra-theme-docs'
import { Callout, Steps } from 'nextra/components'
import { FeatureOverview } from './components/FeatureOverview'
import { ArchitectureOverview } from './components/ArchitectureOverview'
import { IndustryExamples } from './components/IndustryExamples'
import { CommunitySupport } from './components/CommunitySupport'
import { CodeBlock } from './components/CodeBlock'
import { ButtonGroup } from './components/ButtonGroup'
import { FileTree } from './components/FileTree'
import { ThemeAwareImage } from './components/ThemeAwareImage'
import { InfoCardHorizontal } from './components/InfoCardHorizontal'

// Get the default MDX components
const themeComponents = getThemeComponents()

// Merge components
export function useMDXComponents(components) {
  return {
    ...themeComponents,
    ...components,
    // Add Nextra components for Nextra 4
    Callout,
    Steps,
    // Add custom Rhesis components
    FeatureOverview,
    ArchitectureOverview,
    IndustryExamples,
    CommunitySupport,
    CodeBlock,
    ButtonGroup,
    FileTree,
    ThemeAwareImage,
    InfoCardHorizontal,
  }
}
