'use client'

import ChatOutlined from '@mui/icons-material/ChatOutlined'
import BusinessOutlined from '@mui/icons-material/BusinessOutlined'
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined'
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined'
import ShoppingCartOutlined from '@mui/icons-material/ShoppingCartOutlined'
import SchoolOutlined from '@mui/icons-material/SchoolOutlined'

/**
 * IndustryExamples Component
 *
 * A responsive 4-column grid showcasing industry-specific AI use cases
 * that Rhesis helps test and validate.
 *
 * Usage in MDX files:
 * ```mdx
 * <IndustryExamples />
 * ```
 */
const examples = [
  {
    icon: ChatOutlined,
    title: 'Customer Support',
    description:
      'Chatbot in support scenarios - ensuring accurate responses and proper escalation handling',
  },
  {
    icon: BusinessOutlined,
    title: 'Banking',
    description:
      'Financial advisor AI - validating investment recommendations and compliance with regulations',
  },
  {
    icon: VerifiedUserOutlined,
    title: 'Insurance',
    description:
      'Insurance claim processing - automated claim evaluation and fraud detection accuracy',
  },
  {
    icon: AnalyticsOutlined,
    title: 'Business Intelligence',
    description:
      'Executive assistant AI - data analysis, report generation, and strategic insights',
  },
  {
    icon: ShoppingCartOutlined,
    title: 'E-commerce',
    description:
      'Product recommendation engine - testing personalized suggestions and purchase flow accuracy',
  },
  {
    icon: SchoolOutlined,
    title: 'Education',
    description:
      'AI tutoring system - validating lesson explanations and adaptive learning responses',
  },
]

export const IndustryExamples = () => {
  const styles = {
    container: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
      gap: '1.5rem',
      margin: '2rem 0',
    },
    card: {
      textAlign: 'center',
      padding: '1.5rem',
      border: '1px solid',
      borderColor: 'var(--border-color, #e5e7eb)',
      borderRadius: '0.5rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    },
    icon: {
      fontSize: '2rem',
      marginBottom: '0.75rem',
      display: 'block',
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: 'var(--text-primary, #3D3D3D)',
      margin: '0 0 0.75rem 0',
    },
    description: {
      fontSize: '0.875rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.6',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      margin: 0,
    },
  }

  return (
    <>
      <div style={styles.container} className="not-prose rhesis-industry-examples">
        {examples.map((example, index) => (
          <div key={index} style={styles.card}>
            <span style={styles.icon}>
              <example.icon style={{ width: 24, height: 24 }} />
            </span>
            <h3 style={styles.title}>{example.title}</h3>
            <p style={styles.description}>{example.description}</p>
          </div>
        ))}
      </div>

      <style jsx>{`
        [data-theme='dark'] .rhesis-industry-examples {
          --border-color: #30363d;
          --card-bg: #161b22;
          --text-primary: #e6edf3;
          --text-secondary: #a9b1bb;
        }

        [data-theme='light'] .rhesis-industry-examples {
          --border-color: #e5e7eb;
          --card-bg: #ffffff;
          --text-primary: #3d3d3d;
          --text-secondary: #6b7280;
        }

        @media (max-width: 768px) {
          .rhesis-industry-examples {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 1024px) and (min-width: 769px) {
          .rhesis-industry-examples {
            grid-template-columns: repeat(2, 1fr);
          }
        }
      `}</style>
    </>
  )
}

export default IndustryExamples
