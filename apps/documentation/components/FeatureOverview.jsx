'use client'

import React from 'react'
import ScienceOutlined from '@mui/icons-material/ScienceOutlined';
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined';
import DescriptionOutlined from '@mui/icons-material/DescriptionOutlined';
import GroupOutlined from '@mui/icons-material/GroupOutlined';

/**
 * FeatureOverview Component
 *
 * A visually appealing overview of Rhesis platform features.
 * Adapted from Langfuse documentation pattern.
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
    title: "Test Generation",
    items: [
      "AI-powered test scenario creation",
      "Domain expert knowledge integration",
      "Automated edge case coverage",
    ],
  },
  {
    icon: DescriptionOutlined,
    title: "Knowledge Support",
    items: [
      "Upload and store documents",
      "Use documents during test generation",
      "Improve context-based generation",
    ],
  },
  {
    icon: AnalyticsOutlined,
    title: "Evaluation",
    items: [
      "LLM-based quality metrics",
      "Custom evaluation criteria",
      "Detailed performance analytics",
    ],
  },
]

const platformFeature = {
  icon: GroupOutlined,
  title: "Collaborative Platform",
  items: [
    "Team-based project management and organization",
    "SDK and API-first architecture for seamless integration",
    "Comprehensive test result tracking and comparison tools",
  ],
}

export const FeatureOverview = () => {
  const styles = {
    container: {
      display: 'flex',
      flexDirection: 'column',
      margin: '2rem 0',
      padding: '1rem',
      border: '1px solid',
      borderColor: 'var(--border-color, #e5e7eb)',
      borderRadius: '0.5rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
      gap: '1rem',
    },
    gridTop: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
      gap: '1rem',
    },
    card: {
      border: '1px solid',
      borderColor: 'var(--border-color, #e5e7eb)',
      borderRadius: '0.5rem',
      padding: '1.5rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
    },
    cardHeader: {
      display: 'flex',
      alignItems: 'center',
      gap: '0.75rem',
      marginBottom: '1rem',
    },
    icon: {
      color: 'var(--text-primary, #3D3D3D)', // Use text color for neutrality
      flexShrink: 0,
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: 'var(--text-primary, #3D3D3D)',
      margin: 0,
    },
    list: {
      listStyle: 'none',
      padding: 0,
      margin: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
    },
    listItem: {
      display: 'flex',
      alignItems: 'start',
      gap: '0.5rem',
    },
    bullet: {
      width: '0.375rem',
      height: '0.375rem',
      backgroundColor: 'var(--bullet-color, #9CA3AF)', // Subtle gray for bullets
      borderRadius: '50%',
      marginTop: '0.5rem',
      flexShrink: 0,
    },
    itemText: {
      fontSize: '0.875rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.5',
      fontFamily: 'Be Vietnam Pro, sans-serif',
    },
  }

  return (
    <div style={styles.container} className="not-prose rhesis-feature-overview">
      {/* Top 3 cards */}
      <div style={styles.gridTop}>
        {features.map((feature) => (
          <div key={feature.title} style={styles.card}>
            <div style={styles.cardHeader}>
              <feature.icon className="feature-icon" style={styles.icon} />
              <h3 style={styles.title}>{feature.title}</h3>
            </div>
            <ul style={styles.list}>
              {feature.items.map((item, itemIndex) => (
                <li key={itemIndex} style={styles.listItem}>
                  <span style={styles.bullet} />
                  <span style={styles.itemText}>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Platform card - full width */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <platformFeature.icon className="feature-icon" style={styles.icon} />
          <h3 style={styles.title}>{platformFeature.title}</h3>
        </div>
        <ul style={styles.list}>
          {platformFeature.items.map((item, itemIndex) => (
            <li key={itemIndex} style={styles.listItem}>
              <span style={styles.bullet} />
              <span style={styles.itemText}>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <style jsx>{`
        [data-theme="dark"] .rhesis-feature-overview {
          --border-color: #30363d;
          --card-bg: #161B22;
          --text-primary: #E6EDF3;
          --text-secondary: #A9B1BB;
          --bullet-color: #6B7280;
        }

        [data-theme="light"] .rhesis-feature-overview {
          --border-color: #e5e7eb;
          --card-bg: #ffffff;
          --text-primary: #3D3D3D;
          --text-secondary: #6B7280;
          --bullet-color: #9CA3AF;
        }

        @media (max-width: 768px) {
          .rhesis-feature-overview > div:first-child {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  )
}

export default FeatureOverview
