'use client'

import React from 'react'
import CodeOutlined from '@mui/icons-material/CodeOutlined'
import ApiOutlined from '@mui/icons-material/ApiOutlined'
import GroupAddOutlined from '@mui/icons-material/GroupAddOutlined'
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined'
import WebOutlined from '@mui/icons-material/WebOutlined'
import StorageOutlined from '@mui/icons-material/StorageOutlined'
import IntegrationInstructionsOutlined from '@mui/icons-material/IntegrationInstructionsOutlined'
import { InfoCard } from './InfoCard'

/**
 * DevelopmentResourcesGrid Component
 *
 * Displays development resources in a grid layout with icons and links.
 *
 * Usage in MDX files:
 * ```mdx
 * import { DevelopmentResourcesGrid } from '@/components/DevelopmentResourcesGrid'
 *
 * <DevelopmentResourcesGrid />
 * ```
 */

const resources = [
  {
    icon: CodeOutlined,
    title: 'Development Setup',
    description:
      'Complete guide to setting up your development environment for contributing to Rhesis.',
    link: '/docs/development/contributing/development-setup',
    linkText: 'Setup Guide →',
  },
  {
    icon: ApiOutlined,
    title: 'API Structure',
    description: 'Backend REST API architecture, endpoints, and implementation details.',
    link: '/docs/development/backend/api-structure',
    linkText: 'View API Docs →',
  },
  {
    icon: GroupAddOutlined,
    title: 'Contributing',
    description: 'Guidelines and processes for contributing to the Rhesis project.',
    link: '/docs/development/contributing',
    linkText: 'Contribute →',
  },
  {
    icon: CheckCircleOutlined,
    title: 'Coding Standards',
    description:
      'Code style guidelines and best practices for Python, TypeScript, and other languages.',
    link: '/docs/development/contributing/coding-standards',
    linkText: 'View Standards →',
  },
  {
    icon: WebOutlined,
    title: 'Frontend (Platform)',
    description: 'React-based frontend architecture, components, and development patterns.',
    link: '/docs/development/frontend',
    linkText: 'Frontend Docs →',
  },
  {
    icon: StorageOutlined,
    title: 'Backend',
    description: 'FastAPI backend service architecture, database models, and API implementation.',
    link: '/docs/development/backend',
    linkText: 'Backend Docs →',
  },
  {
    icon: IntegrationInstructionsOutlined,
    title: 'SDK',
    description: 'Python SDK documentation for integrating Rhesis into your applications.',
    link: '/docs/sdk',
    linkText: 'SDK Docs →',
  },
]

export const DevelopmentResourcesGrid = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 not-prose">
      {resources.map(resource => (
        <InfoCard
          key={resource.title}
          icon={resource.icon}
          title={resource.title}
          description={resource.description}
          link={resource.link}
          linkText={resource.linkText}
        />
      ))}
    </div>
  )
}

export default DevelopmentResourcesGrid
