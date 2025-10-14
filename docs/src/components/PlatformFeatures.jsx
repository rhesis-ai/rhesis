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
import { InfoCardHorizontal } from './InfoCardHorizontal'

/**
 * PlatformFeatures Component
 *
 * Displays the core features of the Rhesis platform using InfoCardHorizontal.
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
    description: 'Manage organization settings, invite team members, and configure contact information and preferences.',
  },
  {
    icon: FolderIcon,
    title: 'Projects',
    description: 'Organize testing work into projects with environment management, visual icons, and comprehensive project settings.',
  },
  {
    icon: ApiIcon,
    title: 'Endpoints',
    description: 'Configure API endpoints that your tests execute against, with support for REST and WebSocket protocols.',
  },
  {
    icon: AssignmentIcon,
    title: 'Tests',
    description: 'Create and manage test cases manually or generate them using AI with document context and iterative feedback.',
  },
  {
    icon: LibraryBooksIcon,
    title: 'Test Sets',
    description: 'Organize tests into collections and execute them against endpoints with parallel or sequential execution modes.',
  },
  {
    icon: PlayArrowIcon,
    title: 'Test Runs',
    description: 'View execution results for individual test runs with filtering, comparison, and detailed metric analysis.',
  },
  {
    icon: BarChartIcon,
    title: 'Test Results',
    description: 'Dashboard for analyzing test result trends, metrics performance, and historical data with advanced filtering.',
  },
  {
    icon: TuneIcon,
    title: 'Metrics',
    description: 'Define and manage LLM-based evaluation criteria with behaviors, scoring types, and model-driven grading.',
  },
  {
    icon: ExtensionIcon,
    title: 'Integrations',
    description: 'Connect with your existing development workflow and external services.',
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
        />
      ))}
    </div>
  )
}

export default PlatformFeatures
