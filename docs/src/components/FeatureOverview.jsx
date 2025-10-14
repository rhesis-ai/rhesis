'use client'

import React from 'react'
import ScienceOutlined from '@mui/icons-material/ScienceOutlined'
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined'
import CategoryOutlined from '@mui/icons-material/CategoryOutlined'
import ChangeCircleOutlined from '@mui/icons-material/ChangeCircleOutlined'
import IntegrationInstructionsOutlined from '@mui/icons-material/IntegrationInstructionsOutlined'
import { InfoCard } from './InfoCard'

/**
 * FeatureOverview Component
 *
 * A comprehensive overview of Rhesis platform features.
 * Aligned with Webflow website design and messaging.
 *
 * Usage in MDX files:
 * ```mdx
 * import { FeatureOverview } from '@/components/FeatureOverview'
 *
 * <FeatureOverview />
 * ```
 */

const features = [
  {
    icon: ScienceOutlined,
    title: 'Test Generation',
    description: 'Automated scenario creation at scale',
  },
  {
    icon: CategoryOutlined,
    title: 'Knowledge Sets',
    description: 'Domain-specific testing intelligence',
  },
  {
    icon: ChangeCircleOutlined,
    title: 'Test Execution',
    description: 'Real-world simulation engine',
  },
  {
    icon: AnalyticsOutlined,
    title: 'Metrics',
    description: 'Clear insights, actionable results',
  },
  {
    icon: IntegrationInstructionsOutlined,
    title: 'Integrations',
    description: 'Works with your existing stack',
  },
]

export const FeatureOverview = () => {
  const styles = {
    container: {
      margin: '2rem 0',
      maxWidth: '1200px',
      marginLeft: 'auto',
      marginRight: 'auto',
      padding: '0 1rem',
    },
    featuresGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: '1.5rem',
      maxWidth: '900px',
      margin: '0 auto',
    },
  }

  return (
    <div style={styles.container} className="not-prose rhesis-feature-overview">
      {/* Features Grid */}
      <div style={styles.featuresGrid}>
        {features.map(feature => (
          <InfoCard
            key={feature.title}
            icon={feature.icon}
            title={feature.title}
            description={feature.description}
          />
        ))}
      </div>

      <style jsx>{`
        .rhesis-feature-overview .featuresGrid > div:nth-child(4) {
          grid-column: 1 / 2;
          grid-column-start: 1;
          margin-left: 25%;
        }

        .rhesis-feature-overview .featuresGrid > div:nth-child(5) {
          grid-column: 2 / 3;
          margin-right: 25%;
        }

        @media (max-width: 900px) {
          .rhesis-feature-overview .featuresGrid {
            grid-template-columns: repeat(2, 1fr);
            max-width: 600px;
          }

          .rhesis-feature-overview .featuresGrid > div:nth-child(4),
          .rhesis-feature-overview .featuresGrid > div:nth-child(5) {
            grid-column: auto;
            margin-left: 0;
            margin-right: 0;
          }
        }

        @media (max-width: 600px) {
          .rhesis-feature-overview .featuresGrid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  )
}

export default FeatureOverview
