'use client'

import MenuBookOutlined from '@mui/icons-material/MenuBookOutlined'
import ChatOutlined from '@mui/icons-material/ChatOutlined'
import WarningAmberOutlined from '@mui/icons-material/WarningAmberOutlined'

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
    card: {
      textAlign: 'center',
      padding: '1.5rem',
      border: '1px solid',
      borderColor: 'var(--border-color, #e5e7eb)',
      borderRadius: '0.5rem',
      backgroundColor: 'var(--card-bg, #ffffff)',
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: 'var(--text-primary, #111827)',
      margin: '0.5rem 0',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.5rem',
    },
    description: {
      fontSize: '0.875rem',
      color: 'var(--text-secondary, #6B7280)',
      lineHeight: '1.5',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      margin: '0 0 1rem 0',
    },
    link: {
      color: '#2AA1CE',
      textDecoration: 'none',
      fontWeight: '500',
      transition: 'color 0.2s ease',
    },
  }

  return (
    <>
      <div style={styles.container} className="not-prose rhesis-community-support">
        {communityItems.map((item, index) => (
          <div key={index} style={styles.card}>
            <h3 style={styles.title}>
              <item.icon style={{ width: 24, height: 24 }} />
              {item.title}
            </h3>
            <p style={styles.description}>{item.description}</p>
            <a
              href={item.link}
              target={item.external ? '_blank' : '_self'}
              rel={item.external ? 'noopener noreferrer' : undefined}
              style={styles.link}
              className="community-link"
            >
              {item.linkText}
            </a>
          </div>
        ))}
      </div>

      <style jsx>{`
        [data-theme='dark'] .rhesis-community-support {
          --border-color: #374151;
          --card-bg: #1f2937;
          --text-primary: #f9fafb;
          --text-secondary: #d1d5db;
        }

        [data-theme='light'] .rhesis-community-support {
          --border-color: #e5e7eb;
          --card-bg: #ffffff;
          --text-primary: #111827;
          --text-secondary: #6b7280;
        }

        .community-link:hover {
          color: #3bc4f2;
        }

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
