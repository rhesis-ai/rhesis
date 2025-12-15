import { useMDXComponents as getThemeComponents } from 'nextra-theme-docs'
import { Callout, Steps } from 'nextra/components'
import { Mermaid } from './components/MermaidWrapper'
import { FeatureOverview } from './components/FeatureOverview'
import { ArchitectureOverview } from './components/ArchitectureOverview'
import { IndustryExamples } from './components/IndustryExamples'
import { CommunitySupport } from './components/CommunitySupport'
import { CodeBlock } from './components/CodeBlock'
import { ButtonGroup } from './components/ButtonGroup'
import { FileTree } from './components/FileTree'
import { ThemeAwareImage } from './components/ThemeAwareImage'
import { Table } from './components/Table'
import { InfoCardHorizontal } from './components/InfoCardHorizontal'
import { PlatformFeatures } from './components/PlatformFeatures'
import { AdvancedCapabilities } from './components/AdvancedCapabilities'
import { OKLCHColorDemo, ColorSwatch } from './components/OKLCHColorDemo'

// Get the default MDX components
const themeComponents = getThemeComponents()

// Merge components
export function useMDXComponents(components) {
  return {
    ...themeComponents,
    ...components,
    // Add Nextra components
    Callout,
    Steps,
    // Add Mermaid component for diagram rendering
    Mermaid,
    // Add custom Rhesis components
    FeatureOverview,
    ArchitectureOverview,
    IndustryExamples,
    CommunitySupport,
    CodeBlock,
    ButtonGroup,
    FileTree,
    ThemeAwareImage,
    Table,
    InfoCardHorizontal,
    PlatformFeatures,
    AdvancedCapabilities,
    OKLCHColorDemo,
    ColorSwatch,
  }
}
