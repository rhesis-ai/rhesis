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
import MenuBookIcon from '@mui/icons-material/MenuBook'
import PsychologyIcon from '@mui/icons-material/Psychology'
import ModelTrainingIcon from '@mui/icons-material/ModelTraining'
import SettingsInputComponentIcon from '@mui/icons-material/SettingsInputComponent'
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch'
import GroupsIcon from '@mui/icons-material/Groups'
import TimelineIcon from '@mui/icons-material/Timeline'
import TerminalIcon from '@mui/icons-material/Terminal'
import SmartToyIcon from '@mui/icons-material/SmartToy'
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
    description: 'Manage organization settings and invite team members.',
    link: '/docs/organizations',
  },
  {
    icon: FolderIcon,
    title: 'Projects',
    description: 'Organize your testing work into projects.',
    link: '/docs/projects',
  },
  {
    icon: MenuBookIcon,
    title: 'Knowledge',
    description: 'Add sources to generate context-aware test cases.',
    link: '/docs/knowledge',
  },
  {
    icon: PsychologyIcon,
    title: 'Behaviors',
    description: 'Define expected behaviors that your AI application should follow during testing.',
    link: '/docs/behaviors',
  },
  {
    icon: TuneIcon,
    title: 'Metrics',
    description: 'Define and manage LLM-based evaluation criteria.',
    link: '/docs/metrics',
  },
  {
    icon: ApiIcon,
    title: 'Endpoints',
    description: 'Configure the AI application you are testing against.',
    link: '/docs/endpoints',
  },
  {
    icon: ModelTrainingIcon,
    title: 'Models',
    description: 'Configure and manage AI models used for test generation and evaluation.',
    link: '/docs/models',
  },
  {
    icon: AutoFixHighIcon,
    title: 'Test Generation',
    description: 'Generate test cases using AI from knowledge sources and defined behaviors.',
    link: '/docs/tests-generation',
  },
  {
    icon: AssignmentIcon,
    title: 'Tests',
    description: 'Create and manage test cases manually or generate them using AI.',
    link: '/docs/tests',
  },
  {
    icon: LibraryBooksIcon,
    title: 'Test Sets',
    description: 'Organize tests into collections and execute them against your AI application.',
    link: '/docs/test-sets',
  },
  {
    icon: RocketLaunchIcon,
    title: 'Test Execution',
    description: 'Run tests against your endpoints and configure execution parameters.',
    link: '/docs/test-execution',
  },
  {
    icon: PlayArrowIcon,
    title: 'Test Runs',
    description:
      'View execution results for individual test runs with filtering, comparison, and metric analysis.',
    link: '/docs/test-runs',
  },
  {
    icon: BarChartIcon,
    title: 'Results Overview',
    description: 'A global view of all your test results.',
    link: '/docs/results-overview',
  },
  {
    icon: TerminalIcon,
    title: 'Playground',
    description:
      'Interactively test conversational endpoints in real time and convert sessions into tests.',
    link: '/glossary/playground',
  },
  {
    icon: TimelineIcon,
    title: 'Tracing',
    description:
      'OpenTelemetry-based observability for LLM calls, tool invocations, and agent workflows.',
    link: '/tracing',
  },
  {
    icon: GroupsIcon,
    title: 'Collaboration',
    description: 'Coordinate testing work with tasks, inline comments, and human review workflows.',
    link: '/docs/tasks',
  },
  {
    icon: SmartToyIcon,
    title: 'Polyphemus',
    description:
      'Rhesis-hosted open-source LLM service with built-in access control and rate limiting.',
    link: '/glossary/polyphemus',
  },
  {
    icon: SettingsInputComponentIcon,
    title: 'MCP',
    description: 'Connect to Model Context Protocol servers to import knowledge sources.',
    link: '/docs/mcp',
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
