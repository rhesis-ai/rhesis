'use client'

import MenuBookOutlined from '@mui/icons-material/MenuBookOutlined'
import ChatOutlined from '@mui/icons-material/ChatOutlined'
import WarningAmberOutlined from '@mui/icons-material/WarningAmberOutlined'
import { InfoCard } from './InfoCard'

/**
 * CommunitySupport Component
 *
 * A modern, engaging community and support section with enhanced visual design
 * and better user experience following current documentation site best practices.
 *
 * Usage in MDX files:
 * ```mdx
 * <CommunitySupport />
 * ```
 */

const communityItems = [
  {
    icon: MenuBookOutlined,
    title: 'Documentation',
    description: 'Comprehensive guides and API references',
    link: '/platform',
    linkText: 'Browse Docs →',
  },
  {
    icon: ChatOutlined,
    title: 'Community',
    description: 'Join discussions and get help from the community',
    link: 'https://github.com/rhesis-ai/rhesis/discussions',
    linkText: 'GitHub Discussions →',
    external: true,
  },
  {
    icon: WarningAmberOutlined,
    title: 'Issues',
    description: 'Report bugs and request features',
    link: 'https://github.com/rhesis-ai/rhesis/issues',
    linkText: 'GitHub Issues →',
    external: true,
  },
]

export const CommunitySupport = () => {
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
      <div style={styles.container} className="not-prose rhesis-community-support">
        {communityItems.map((item) => (
          <InfoCard
            key={item.title}
            icon={item.icon}
            title={item.title}
            description={item.description}
            link={item.link}
            linkText={item.linkText}
            external={item.external}
          />
        ))}
      </div>

      <style jsx>{`
        @media (max-width: 768px) {
          .rhesis-community-support {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 1024px) and (min-width: 769px) {
          .rhesis-community-support {
            grid-template-columns: repeat(2, 1fr);
          }
        }
      `}</style>
    </>
  )
}

export default CommunitySupport
