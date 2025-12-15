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
  product: {
    title: 'Product',
    links: [
      { name: 'Platform', href: 'https://app.rhesis.ai', external: true },
      { name: 'SDK', href: '/sdk' },
      { name: 'Repository', href: 'https://github.com/rhesis-ai/rhesis', external: true },
    ],
  },
  docs: {
    title: 'Docs',
    links: [
      { name: 'Getting started', href: '/getting-started/self-hosting' },
      { name: 'Test Generation', href: '/platform/tests-generation' },
      { name: 'Metrics', href: '/platform/metrics' },
    ],
  },
  company: {
    title: 'Company',
    links: [
      { name: 'About us', href: 'https://www.rhesis.ai/about-us', external: true },
      { name: 'Careers', href: 'https://rhesis-ai.jobs.personio.com/', external: true },
      { name: 'Contact us', href: 'https://www.rhesis.ai/contact-us', external: true },
    ],
  },
}

const legalLinks = [
  { name: 'Imprint', href: 'https://www.rhesis.ai/imprint', external: true },
  { name: 'Privacy', href: 'https://www.rhesis.ai/privacy-policy', external: true },
  {
    name: 'Terms',
    href: 'https://www.rhesis.ai/terms-conditions',
    external: true,
  },
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
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
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
    legalLinks: {
      display: 'flex',
      gap: '1.5rem',
      flexWrap: 'wrap',
    },
    legalLink: {
      color: 'var(--text-secondary, #e5e7eb)',
      textDecoration: 'none',
      fontSize: '0.75rem',
      fontFamily: 'Be Vietnam Pro, sans-serif',
      transition: 'color 0.2s ease',
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

          {/* Bottom section with copyright and legal links */}
          <div style={styles.bottom}>
            {showCopyright && (
              <div style={styles.copyright}>
                Copyright ©{currentYear} Rhesis AI GmbH • Made in Potsdam, Germany.
              </div>
            )}

            <div style={styles.legalLinks}>
              {legalLinks.map(link => (
                <a
                  key={`legal-${link.name}`}
                  href={link.href}
                  target={link.external ? '_blank' : '_self'}
                  rel={link.external ? 'noopener noreferrer' : undefined}
                  style={styles.legalLink}
                  className="footer-legal-link"
                >
                  {link.name}
                </a>
              ))}
              {/* Add any additional legal links */}
              {additionalLinks
                .filter(link => link.section === 'legal')
                .map(link => (
                  <a
                    key={`legal-additional-${link.name}`}
                    href={link.href}
                    target={link.external ? '_blank' : '_self'}
                    rel={link.external ? 'noopener noreferrer' : undefined}
                    style={styles.legalLink}
                    className="footer-legal-link"
                  >
                    {link.name}
                  </a>
                ))}
            </div>
          </div>
        </div>
      </footer>

      <style jsx global>{`
        /* Rhesis brand footer theme */
        .rhesis-footer {
          --border-color: var(--rhesis-primary-main);
          --footer-bg: var(--rhesis-primary-dark);
          --text-primary: #ffffff;
          --text-secondary: rgba(255, 255, 255, 0.8);
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

        /* Light theme adjustments */
        [data-theme='light'] .rhesis-footer {
          --border-color: var(--rhesis-primary-main);
          --footer-bg: var(--rhesis-primary-dark);
          --text-primary: #ffffff;
          --text-secondary: rgba(255, 255, 255, 0.8);
          --logo-bg: #ffffff;
        }

        /* System theme fallback - only when no explicit theme is set */
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
        .footer-link:hover,
        .footer-legal-link:hover {
          color: var(--rhesis-accent-yellow);
        }

        /* Responsive design */
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

          .rhesis-footer div[style*='gap: 1.5rem'] {
            gap: 1rem;
            flex-direction: column;
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
        .footer-legal-link:focus {
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
