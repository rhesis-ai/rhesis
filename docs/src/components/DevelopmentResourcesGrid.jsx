'use client'

import React from 'react'
import CodeOutlined from '@mui/icons-material/CodeOutlined'
import ApiOutlined from '@mui/icons-material/ApiOutlined'
import GroupAddOutlined from '@mui/icons-material/GroupAddOutlined'
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined'
import WebOutlined from '@mui/icons-material/WebOutlined'
import StorageOutlined from '@mui/icons-material/StorageOutlined'
import IntegrationInstructionsOutlined from '@mui/icons-material/IntegrationInstructionsOutlined'
import { ResourceCard } from './ResourceCard'

/**
 * DevelopmentResourcesGrid Component
 *
 * Displays development resources in a grid layout with squared cards.
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
    description: 'Complete guide to setting up your development environment.',
    link: '/development/contributing/development-setup',
    linkText: 'Setup Guide →',
  },
  {
    icon: StorageOutlined,
    title: 'Backend',
    description: 'FastAPI backend service architecture.',
    link: '/development/backend',
    linkText: 'Backend Docs →',
  },
  {
    icon: WebOutlined,
    title: 'Frontend',
    description: 'React-based frontend architecture.',
    link: '/development/frontend',
    linkText: 'Frontend Docs →',
  },
  {
    icon: ApiOutlined,
    title: 'API Structure',
    description: 'Backend REST API architecture and endpoints.',
    link: '/development/backend/api-structure',
    linkText: 'View API Docs →',
  },
  {
    icon: IntegrationInstructionsOutlined,
    title: 'SDK',
    description: 'Python SDK documentation.',
    link: '/sdk',
    linkText: 'SDK Docs →',
  },
  {
    icon: CheckCircleOutlined,
    title: 'Coding Standards',
    description: 'Code style guidelines and best practices.',
    link: '/development/contributing/coding-standards',
    linkText: 'View Standards →',
  },
  {
    icon: GroupAddOutlined,
    title: 'Contributing',
    description: 'Guidelines for contributing to Rhesis.',
    link: '/development/contributing',
    linkText: 'Contribute →',
  },
]

export const DevelopmentResourcesGrid = () => {
  return (
    <div
      className="not-prose"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: '1rem',
        marginTop: '1.5rem',
        marginBottom: '1.5rem',
      }}
    >
      {resources.map(resource => (
        <ResourceCard
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
