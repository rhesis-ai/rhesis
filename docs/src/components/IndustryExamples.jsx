'use client'

import GroupsOutlined from '@mui/icons-material/GroupsOutlined'
import IntegrationInstructionsOutlined from '@mui/icons-material/IntegrationInstructionsOutlined'
import VerifiedOutlined from '@mui/icons-material/VerifiedOutlined'
import { InfoCardHorizontal } from './InfoCardHorizontal'

/**
 * IndustryExamples Component
 *
 * Showcases team collaboration and platform capabilities using horizontal cards.
 * Ideal for highlighting key features and benefits.
 *
 * Usage in MDX files:
 * ```mdx
 * <IndustryExamples />
 * ```
 */
const examples = [
  {
    icon: GroupsOutlined,
    title: 'Collaborative by Design',
    description:
      'Bring together developers, domain experts, legal teams, and marketing to define comprehensive test scenarios. Everyone contributes their expertise through an intuitive interface.',
  },
  {
    icon: IntegrationInstructionsOutlined,
    title: 'Works with Any Gen AI System',
    description:
      'Seamlessly integrates with your existing tech stack. Whether you use OpenAI, Anthropic, custom models, or RAG systems, Rhesis adapts to your architecture.',
  },
  {
    icon: VerifiedOutlined,
    title: 'Ship with Confidence',
    description:
      'Know exactly how your Gen AI behaves before users see it. Comprehensive test coverage across edge cases, failure modes, and real-world scenarios ensures reliable releases.',
  },
]

export const IndustryExamples = () => {
  const styles = {
    container: {
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
      margin: '2rem 0',
    },
  }

  return (
    <div style={styles.container} className="not-prose rhesis-industry-examples">
      {examples.map(example => (
        <InfoCardHorizontal
          key={example.title}
          icon={example.icon}
          title={example.title}
          description={example.description}
        />
      ))}
    </div>
  )
}

export default IndustryExamples
