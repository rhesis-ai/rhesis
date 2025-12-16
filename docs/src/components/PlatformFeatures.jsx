'use client'

import React from 'react'
import BusinessIcon from '@mui/icons-material/Business'
import FolderIcon from '@mui/icons-material/Folder'
import ApiIcon from '@mui/icons-material/Api'
import AssignmentIcon from '@mui/icons-material/Assignment'
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import BarChartIcon from '@mui/icons-material/BarChart'
import TuneIcon from '@mui/icons-material/Tune'
import ExtensionIcon from '@mui/icons-material/Extension'
import VpnKeyIcon from '@mui/icons-material/VpnKey'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import PsychologyIcon from '@mui/icons-material/Psychology'
import ModelTrainingIcon from '@mui/icons-material/ModelTraining'
import SettingsInputComponentIcon from '@mui/icons-material/SettingsInputComponent'
import { InfoCardHorizontal } from './InfoCardHorizontal'

/**
 * PlatformFeatures Component
 *
 * Displays all features and capabilities of the Rhesis platform using InfoCardHorizontal.
 * All features are clickable and link to their respective documentation pages.
 *
 * Usage in MDX files:
 * ```mdx
 * import { PlatformFeatures } from '@/components/PlatformFeatures'
 *
 * <PlatformFeatures />
 * ```
 */

const features = [
  {
    icon: BusinessIcon,
    title: 'Organizations & Team',
    description:
      'Manage organization settings and invite team members.',
    link: '/platform/organizations',
  },
  {
    icon: FolderIcon,
    title: 'Projects',
    description:
      'Organize your testing work into projects.',
    link: '/platform/projects',
  },
  {
    icon: MenuBookIcon,
    title: 'Knowledge',
    description:
      'Add sources to generate context-aware test cases.',
    link: '/platform/knowledge',
  },
  {
    icon: PsychologyIcon,
    title: 'Behaviors',
    description:
      'Define expected behaviors that your AI application should follow during testing.',
    link: '/platform/behaviors',
  },
  {
    icon: TuneIcon,
    title: 'Metrics',
    description:
      'Define and manage LLM-based evaluation criteria.',
    link: '/platform/metrics',
  },
  {
    icon: ApiIcon,
    title: 'Endpoints',
    description:
      'Configure the AI application you are testing against.',
    link: '/platform/endpoints',
  },
  {
    icon: ModelTrainingIcon,
    title: 'Models',
    description:
      'Configure and manage AI models used for test generation and evaluation.',
    link: '/platform/models',
  },
  {
    icon: AssignmentIcon,
    title: 'Tests',
    description:
      'Create and manage test cases manually or generate them using AI.',
    link: '/platform/tests',
  },
  {
    icon: LibraryBooksIcon,
    title: 'Test Sets',
    description:
      'Organize tests into collections and execute them against your AI application.',
    link: '/platform/test-sets',
  },
  {
    icon: PlayArrowIcon,
    title: 'Test Runs',
    description:
      'View execution results for individual test runs with filtering, comparison, and metric analysis.',
    link: '/platform/test-runs',
  },
  {
    icon: BarChartIcon,
    title: 'Results Overview',
    description:
      'A global view of all your test results.',
    link: '/platform/results-overview',
  },
  {
    icon: SettingsInputComponentIcon,
    title: 'MCP',
    description:
      'Connect to Model Context Protocol servers to import knowledge sources.',
    link: '/platform/mcp',
  },
]

export const PlatformFeatures = () => {
  const containerStyles = {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '0.75rem',
    maxWidth: '1000px',
    marginLeft: 'auto',
    marginRight: 'auto',
    marginTop: '1.5rem',
  }

  return (
    <div style={containerStyles} className="not-prose platform-features-compact">
      {features.map(feature => (
        <InfoCardHorizontal
          key={feature.title}
          icon={feature.icon}
          title={feature.title}
          description={feature.description}
          link={feature.link}
          linkText="Learn more →"
        />
      ))}
    </div>
  )
}

export default PlatformFeatures
