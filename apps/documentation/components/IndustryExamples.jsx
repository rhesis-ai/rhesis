'use client'

import ChatOutlined from '@mui/icons-material/ChatOutlined'
import BusinessOutlined from '@mui/icons-material/BusinessOutlined'
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined'
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined'
import ShoppingCartOutlined from '@mui/icons-material/ShoppingCartOutlined'
import SchoolOutlined from '@mui/icons-material/SchoolOutlined'
import { InfoCard } from './InfoCard'

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
  }

  return (
    <>
      <div style={styles.container} className="not-prose rhesis-industry-examples">
        {examples.map((example, index) => (
          <InfoCard
            key={index}
            icon={example.icon}
            title={example.title}
            description={example.description}
          />
        ))}
      </div>

      <style jsx>{`
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
