import { useMDXComponents as getThemeComponents, Callout, Steps } from 'nextra-theme-docs'
import { FeatureOverview } from './components/FeatureOverview'
import { ArchitectureOverview } from './components/ArchitectureOverview'
import { IndustryExamples } from './components/IndustryExamples'
import { CommunitySupport } from './components/CommunitySupport'
import { CodeBlock } from './components/CodeBlock'
import { ButtonGroup } from './components/ButtonGroup'
import { FileTree } from './components/FileTree'
import { ThemeAwareImage } from './components/ThemeAwareImage'
import { InfoCardHorizontal } from './components/InfoCardHorizontal'
import { PlatformFeatures } from './components/PlatformFeatures'
import { AdvancedCapabilities } from './components/AdvancedCapabilities'

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
    PlatformFeatures,
    AdvancedCapabilities,
  }
}
