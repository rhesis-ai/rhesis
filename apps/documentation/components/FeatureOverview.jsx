'use client'

import React from 'react'

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

// Simple SVG icon components (replacing lucide-react dependency)
const TestIcon = ({ className = "" }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
  </svg>
)

const MetricsIcon = ({ className = "" }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
)

const EndpointsIcon = ({ className = "" }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
)

const CollaborationIcon = ({ className = "" }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
  </svg>
)

const features = [
  {
    icon: TestIcon,
    title: "Test Generation",
    items: [
      "AI-powered test scenario creation",
      "Domain expert knowledge integration",
      "Automated edge case coverage",
    ],
  },
  {
    icon: EndpointsIcon,
    title: "Endpoints",
    items: [
      "REST and WebSocket support",
      "Multi-provider LLM integration",
      "Real-time testing execution",
    ],
  },
  {
    icon: MetricsIcon,
    title: "Evaluation",
    items: [
      "LLM-based quality metrics",
      "Custom evaluation criteria",
      "Detailed performance analytics",
    ],
  },
]

const platformFeature = {
  icon: CollaborationIcon,
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
      width: '1.25rem',
      height: '1.25rem',
      color: '#2AA1CE', // Rhesis primary blue
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
      backgroundColor: '#2AA1CE', // Rhesis primary blue
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
              <feature.icon style={styles.icon} />
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
          <platformFeature.icon style={styles.icon} />
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
        }

        [data-theme="light"] .rhesis-feature-overview {
          --border-color: #e5e7eb;
          --card-bg: #ffffff;
          --text-primary: #3D3D3D;
          --text-secondary: #6B7280;
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
