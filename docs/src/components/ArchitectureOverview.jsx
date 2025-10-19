'use client'

import React from 'react'
import ScienceOutlined from '@mui/icons-material/ScienceOutlined'
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined'
import CategoryOutlined from '@mui/icons-material/CategoryOutlined'
import ChangeCircleOutlined from '@mui/icons-material/ChangeCircleOutlined'
import IntegrationInstructionsOutlined from '@mui/icons-material/IntegrationInstructionsOutlined'
import GroupWorkOutlined from '@mui/icons-material/GroupWorkOutlined'
import { InfoCardHorizontal } from './InfoCardHorizontal'

/**
 * ArchitectureOverview Component
 *
 * Displays the Rhesis project architecture components using InfoCardHorizontal.
 *
 * Usage in MDX files:
 * ```mdx
 * import { ArchitectureOverview } from '@/components/ArchitectureOverview'
 *
 * <ArchitectureOverview />
 * ```
 */

const architectureComponents = [
  {
    icon: ScienceOutlined,
    title: 'Backend Service',
    description:
      'FastAPI-based backend service providing REST APIs, authentication, and business logic.',
  },
  {
    icon: CategoryOutlined,
    title: 'Frontend Application',
    description: 'React-based frontend with TypeScript, providing the main user interface.',
  },
  {
    icon: ChangeCircleOutlined,
    title: 'Worker Service',
    description: 'Celery-based background task processing for long-running operations.',
  },
  {
    icon: GroupWorkOutlined,
    title: 'Chatbot Application',
    description: 'AI-powered chatbot for interactive testing and evaluation.',
  },
  {
    icon: AnalyticsOutlined,
    title: 'Monitoring Service',
    description: 'Polyphemus service for observability and monitoring.',
  },
  {
    icon: IntegrationInstructionsOutlined,
    title: 'Python SDK',
    description: 'Comprehensive Python SDK for integrating Rhesis into your applications.',
  },
]

export const ArchitectureOverview = () => {
  const styles = {
    container: {
      display: 'grid',
      gridTemplateColumns: 'repeat(1, 1fr)',
      gap: '1rem',
      margin: '0',
    },
    '@media (min-width: 1024px)': {
      container: {
        gridTemplateColumns: 'repeat(2, 1fr)',
      },
    },
  }

  return (
    <div
      style={styles.container}
      className="not-prose rhesis-architecture-overview grid grid-cols-1 lg:grid-cols-2 gap-4"
    >
      {architectureComponents.map(component => (
        <InfoCardHorizontal
          key={component.title}
          icon={component.icon}
          title={component.title}
          description={component.description}
        />
      ))}
    </div>
  )
}

export default ArchitectureOverview
