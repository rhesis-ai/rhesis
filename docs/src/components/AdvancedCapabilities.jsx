'use client'

import React from 'react'
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'
import AssessmentIcon from '@mui/icons-material/Assessment'
import CollectionsIcon from '@mui/icons-material/Collections'
import VpnKeyIcon from '@mui/icons-material/VpnKey'
import GroupsIcon from '@mui/icons-material/Groups'
import { InfoCardHorizontal } from './InfoCardHorizontal'

/**
 * AdvancedCapabilities Component
 *
 * Displays the advanced capabilities of the Rhesis platform using InfoCardHorizontal.
 *
 * Usage in MDX files:
 * ```mdx
 * import { AdvancedCapabilities } from '@/components/AdvancedCapabilities'
 *
 * <AdvancedCapabilities />
 * ```
 */

const capabilities = [
  {
    icon: PlayCircleOutlineIcon,
    title: 'Test Runs',
    description: 'Deep analysis with comparison and filtering',
  },
  {
    icon: AssessmentIcon,
    title: 'Test Results',
    description: 'Aggregate analytics and trend visualization',
  },
  {
    icon: CollectionsIcon,
    title: 'Test Sets',
    description: 'Organize and execute test collections',
  },
  {
    icon: VpnKeyIcon,
    title: 'API Tokens',
    description: 'Programmatic access via Python SDK',
  },
  {
    icon: GroupsIcon,
    title: 'Organizations',
    description: 'Team management and access control',
  },
]

export const AdvancedCapabilities = () => {
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
      {capabilities.map(capability => (
        <InfoCardHorizontal
          key={capability.title}
          icon={capability.icon}
          title={capability.title}
          description={capability.description}
        />
      ))}
    </div>
  )
}

export default AdvancedCapabilities
