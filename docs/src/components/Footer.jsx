'use client'

/**
 * Footer Component
 *
 * A comprehensive, reusable footer component that matches the main Rhesis website
 * structure with proper theming and responsive design.
 *
 * Usage:
 * ```jsx
 * import Footer from './components/Footer'
 * <Footer />
 * ```
 *
 * The component is extensible and can be customized by passing props:
 * ```jsx
 * <Footer
 *   showCopyright={true}
 *   additionalLinks={[...]}
 *   customSections={[...]}
 * />
 * ```
 */

const footerData = {
  features: {
    title: 'Features',
    links: [
      { name: 'Test Generation', href: '/platform/tests-generation' },
      { name: 'Metrics', href: '/platform/metrics' },
      { name: 'Conversations', href: '/penelope' },
      { name: 'Observability', href: '/tracing' },
    ],
  },
  resources: {
    title: 'Resources',
    links: [
      { name: 'Watch Demo', href: 'https://www.rhesis.ai/watch-demo', external: true },
      { name: 'Try Demo', href: 'https://app.rhesis.ai/demo', external: true },
      { name: 'Documentation', href: '/' },
      { name: 'API Reference', href: 'https://rhesis-sdk.readthedocs.io/en/latest/', external: true },
      { name: 'Blog', href: 'https://www.rhesis.ai/blog', external: true },
    ],
  },
  guides: {
    title: 'Guides',
    links: [
      { name: 'Quick Start Guide', href: '/guides/quick-start-guide' },
      { name: 'SDK Connector', href: '/sdk/connector' },
      { name: 'CI/CD Integration', href: '/guides/ci-cd-integration' },
      { name: 'Custom Metrics', href: '/guides/custom-metrics' },
    ],
  },
  company: {
    title: 'Company',
    links: [
      { name: 'About us', href: 'https://www.rhesis.ai/about', external: true },
      { name: 'Careers', href: 'https://rhesis-ai.jobs.personio.com/', external: true },
      { name: 'Contact us', href: 'https://www.rhesis.ai/talk-to-us', external: true },
    ],
  },
  legal: {
    title: 'Legal',
    links: [
      { name: 'Privacy', href: 'https://www.rhesis.ai/privacy-policy', external: true },
      { name: 'Terms', href: 'https://www.rhesis.ai/terms-conditions', external: true },
      { name: 'Imprint', href: 'https://www.rhesis.ai/imprint', external: true },
    ],
  },
}

const socialLinks = [
  { name: 'Discord', href: 'https://discord.rhesis.ai', external: true },
  { name: 'GitHub', href: 'https://github.com/rhesis-ai/rhesis', external: true },
  { name: 'LinkedIn', href: 'https://www.linkedin.com/company/101972349', external: true },
]

export const Footer = ({
  showCopyright = true,
  additionalLinks = [],
  customSections = [],
  className = '',
}) => {
  const currentYear = new Date().getFullYear()

  const allSections = [...Object.values(footerData), ...customSections]

  const styles = {
    footer: {
      borderTop: '1px solid',
      borderColor: 'var(--border-color, var(--rhesis-primary-main))',
      backgroundColor: 'var(--footer-bg, var(--rhesis-primary-dark))',
      color: 'var(--text-primary, #ffffff)',
      marginTop: 'auto',
    },
    container: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '3rem 1.5rem 2rem',
    },
    topSection: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '3rem',
      marginBottom: '2rem',
    },
    logoSection: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      minWidth: '100px',
    },
    logoCircle: {
      width: '120px',
      height: '120px',
      borderRadius: '50%',
      backgroundColor: 'var(--logo-bg, #ffffff)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: '0',
      padding: '10px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    },
    logoImage: {
      width: '100%',
      height: '100%',
      objectFit: 'contain',
    },
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(5, 1fr)',
      gap: '2rem',
      flex: '1',
    },
    section: {
      display: 'flex',
      flexDirection: 'column',
    },
    sectionTitle: {
      fontSize: '0.875rem',
      fontWeight: '600',
      fontFamily: 'Sora, sans-serif',
      color: 'var(--text-primary, #ffffff)',
      marginBottom: '1rem',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    },
    linkList: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      listStyle: 'none',
      margin: 0,
      padding: 0,
    },
    link: {
      color: 'var(--text-secondary, #e5e7eb)',
      textDecoration: 'none',
      fontSize: '0.875rem',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      transition: 'color 0.2s ease',
      lineHeight: '1.5',
    },
    bottom: {
      borderTop: '1px solid',
      borderColor: 'var(--border-color, rgba(255, 255, 255, 0.2))',
      paddingTop: '1.5rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
    },
    copyright: {
      fontSize: '0.75rem',
      color: 'var(--text-secondary, #e5e7eb)',
      fontFamily: 'Be Vietnam Pro, sans-serif',
    },
    socialLinks: {
      display: 'flex',
      gap: '1rem',
      alignItems: 'center',
    },
    socialLink: {
      color: 'var(--text-secondary, #e5e7eb)',
      textDecoration: 'none',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '32px',
      height: '32px',
      borderRadius: '4px',
      transition: 'all 0.2s ease',
    },
  }

  return (
    <>
      <footer style={styles.footer} className={`rhesis-footer ${className}`}>
        <div style={styles.container}>
          {/* Top section with logo and links */}
          <div style={styles.topSection}>
            {/* Logo section */}
            <div style={styles.logoSection}>
              <div style={styles.logoCircle}>
                <img
                  src="/logo/rhesis-logo-rgb-isotype.png"
                  alt="Rhesis Logo"
                  style={styles.logoImage}
                />
              </div>
            </div>

            {/* Main footer sections */}
            <div style={styles.grid}>
              {allSections.map(section => (
                <div key={section.title} style={styles.section}>
                  <h3 style={styles.sectionTitle}>{section.title}</h3>
                  <ul style={styles.linkList}>
                    {section.links.map(link => (
                      <li key={`${section.title}-${link.name}`}>
                        <a
                          href={link.href}
                          target={link.external ? '_blank' : '_self'}
                          rel={link.external ? 'noopener noreferrer' : undefined}
                          style={styles.link}
                          className="footer-link"
                        >
                          {link.name}
                        </a>
                      </li>
                    ))}
                    {/* Add any additional links for this section */}
                    {additionalLinks
                      .filter(link => link.section === section.title.toLowerCase())
                      .map(link => (
                        <li key={`${section.title}-additional-${link.name || link.href}`}>
                          <a
                            href={link.href}
                            target={link.external ? '_blank' : '_self'}
                            rel={link.external ? 'noopener noreferrer' : undefined}
                            style={styles.link}
                            className="footer-link"
                          >
                            {link.name}
                          </a>
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom section with copyright and social media */}
          <div style={styles.bottom}>
            {showCopyright && (
              <div style={styles.copyright}>
                Copyright ©{currentYear} Rhesis AI GmbH • Made in Potsdam, Germany.
              </div>
            )}

            <div style={styles.socialLinks}>
              {socialLinks.map(link => (
                <a
                  key={`social-${link.name}`}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.socialLink}
                  className="footer-social-link"
                  aria-label={link.name}
                >
                  {link.name === 'Discord' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                    </svg>
                  )}
                  {link.name === 'GitHub' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                  )}
                  {link.name === 'LinkedIn' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                  )}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>

      <style jsx global>{`
        /* Rhesis brand footer theme - matching website */
        .rhesis-footer {
          --border-color: var(--rhesis-accent-yellow);
          --footer-bg: var(--rhesis-accent-yellow);
          --text-primary: #1a1a1a;
          --text-secondary: #3d3d3d;
          --logo-bg: #ffffff;
        }

        /* Dark theme adjustments */
        [data-theme='dark'] .rhesis-footer,
        .dark .rhesis-footer {
          --border-color: rgba(255, 255, 255, 0.1);
          --footer-bg: #0d1117;
          --text-primary: #e6edf3;
          --text-secondary: rgba(230, 237, 243, 0.7);
          --logo-bg: #ffffff;
        }

        /* Light theme adjustments - matching website */
        [data-theme='light'] .rhesis-footer {
          --border-color: var(--rhesis-accent-yellow);
          --footer-bg: var(--rhesis-accent-yellow);
          --text-primary: #1a1a1a;
          --text-secondary: #3d3d3d;
          --logo-bg: #ffffff;
        }

        /* System theme fallback - light mode by default */
        @media (prefers-color-scheme: light) {
          html:not([data-theme]) .rhesis-footer {
            --border-color: var(--rhesis-accent-yellow);
            --footer-bg: var(--rhesis-accent-yellow);
            --text-primary: #1a1a1a;
            --text-secondary: #3d3d3d;
            --logo-bg: #ffffff;
          }
        }

        /* System theme fallback - dark mode */
        @media (prefers-color-scheme: dark) {
          html:not([data-theme]) .rhesis-footer {
            --border-color: rgba(255, 255, 255, 0.1);
            --footer-bg: #0d1117;
            --text-primary: #e6edf3;
            --text-secondary: rgba(230, 237, 243, 0.7);
            --logo-bg: #ffffff;
          }
        }

        /* Hover effects */
        .footer-link:hover {
          color: var(--rhesis-primary-dark);
          opacity: 0.8;
        }

        .footer-social-link:hover {
          opacity: 0.7;
        }

        /* Dark mode hover effects */
        [data-theme='dark'] .footer-link:hover,
        .dark .footer-link:hover {
          color: var(--rhesis-accent-yellow);
          opacity: 1;
        }

        [data-theme='dark'] .footer-social-link:hover,
        .dark .footer-social-link:hover {
          color: var(--rhesis-accent-yellow);
          background-color: rgba(253, 216, 3, 0.1);
          opacity: 1;
        }

        /* Responsive design */
        @media (max-width: 1024px) {
          .rhesis-footer div[style*='grid-template-columns'] {
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
          }
        }

        @media (max-width: 768px) {
          .rhesis-footer div[style*='display: flex'][style*='align-items: flex-start'] {
            flex-direction: column;
            gap: 2rem;
          }

          .rhesis-footer div[style*='grid-template-columns'] {
            grid-template-columns: repeat(2, 1fr);
            gap: 1.5rem;
          }

          .rhesis-footer div[style*='flex-direction: column'] {
            align-items: flex-start;
          }
        }

        @media (max-width: 480px) {
          .rhesis-footer div[style*='grid-template-columns'] {
            grid-template-columns: 1fr;
          }

          .rhesis-footer div[style*='padding: 3rem 1.5rem 2rem'] {
            padding: 2rem 1rem 1.5rem;
          }

          .rhesis-footer div[style*='min-width: 100px'] {
            min-width: auto;
            align-items: center;
          }
        }

        /* Ensure footer sticks to bottom */
        .rhesis-footer {
          margin-top: auto;
        }

        /* Accessibility improvements */
        .footer-link:focus,
        .footer-social-link:focus {
          outline: 2px solid var(--rhesis-accent-yellow);
          outline-offset: 2px;
          border-radius: 2px;
        }

        /* Print styles */
        @media print {
          .rhesis-footer {
            display: none;
          }
        }
      `}</style>
    </>
  )
}

export default Footer
