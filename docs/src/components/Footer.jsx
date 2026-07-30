/**
 * Footer
 *
 * Ported from the marketing site's footer (Figma 2351:1625): neutral canvas,
 * brand column plus four link columns with Geist Mono uppercase headers, and a
 * bottom bar carrying the copyright and social channels. Styling lives in the
 * "FOOTER" section of globals.css.
 *
 * Link sets stay docs-specific — the shape is shared with the site, the content
 * is not.
 */

import { FooterOriginBadge } from './FooterOriginBadge'

const footerColumns = [
  {
    key: 'features',
    title: 'Features',
    links: [
      { name: 'Generation', href: '/docs/test-sets/tests-generation' },
      { name: 'Metrics', href: '/docs/metrics' },
      { name: 'Conversations', href: '/docs/tests/conversation-simulation' },
      { name: 'Observability', href: '/docs/tracing' },
    ],
  },
  {
    key: 'guides',
    title: 'Guides',
    links: [
      { name: 'Quick start guide', href: '/guides/quick-start-guide' },
      { name: 'SDK connector', href: '/sdk/connector' },
      { name: 'CI/CD integration', href: '/guides/ci-cd-integration' },
      { name: 'Testing user journeys', href: '/guides/testing-user-journeys' },
    ],
  },
  {
    key: 'glossary',
    title: 'Glossary',
    links: [
      { name: 'LLM as a Judge', href: '/glossary/llm-as-a-judge' },
      { name: 'Test Generation', href: '/glossary/test-generation' },
      { name: 'Trace', href: '/glossary/trace' },
      { name: 'Agent', href: '/glossary/agent' },
    ],
  },
  {
    key: 'company',
    title: 'Company',
    links: [
      { name: 'About us', href: 'https://www.rhesis.ai/about', external: true },
      { name: 'Careers', href: 'https://rhesis-ai.jobs.personio.com/', external: true },
      { name: 'Contact us', href: 'https://www.rhesis.ai/talk-to-us', external: true },
    ],
  },
]

const legalLinks = [
  { name: 'Imprint', href: 'https://www.rhesis.ai/imprint' },
  { name: 'Privacy', href: 'https://www.rhesis.ai/privacy-policy' },
  { name: 'Terms', href: 'https://www.rhesis.ai/terms-conditions' },
]

/* Figma order: GitHub, Discord, LinkedIn, X, YouTube */
const socialLinks = [
  {
    name: 'GitHub',
    href: 'https://github.com/rhesis-ai/rhesis',
    viewBox: '0 0 16 16',
    path: 'M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z',
  },
  {
    name: 'Discord',
    href: 'https://discord.rhesis.ai',
    viewBox: '0 0 16 16',
    path: 'M13.545 2.907a13.2 13.2 0 0 0-3.257-1.011.05.05 0 0 0-.052.025c-.141.25-.297.577-.406.833a12.2 12.2 0 0 0-3.658 0 8 8 0 0 0-.412-.833.05.05 0 0 0-.052-.025c-1.125.194-2.22.534-3.257 1.011a.04.04 0 0 0-.021.018C.356 6.024-.213 9.047.066 12.032q.003.022.021.037a13.3 13.3 0 0 0 3.995 2.02.05.05 0 0 0 .056-.019q.463-.63.818-1.329a.05.05 0 0 0-.01-.059l-.018-.011a9 9 0 0 1-1.248-.595.05.05 0 0 1-.02-.066l.015-.019q.127-.095.248-.195a.05.05 0 0 1 .051-.007c2.619 1.196 5.454 1.196 8.041 0a.05.05 0 0 1 .053.007q.121.1.248.195a.05.05 0 0 1-.004.085 8 8 0 0 1-1.249.594.05.05 0 0 0-.03.03.05.05 0 0 0 .003.041c.24.465.515.909.817 1.329a.05.05 0 0 0 .056.019 13.2 13.2 0 0 0 4.001-2.02.05.05 0 0 0 .021-.037c.334-3.451-.559-6.449-2.366-9.106a.03.03 0 0 0-.02-.019m-8.198 7.307c-.789 0-1.438-.724-1.438-1.612s.637-1.613 1.438-1.613c.807 0 1.45.73 1.438 1.613 0 .888-.637 1.612-1.438 1.612m5.316 0c-.788 0-1.438-.724-1.438-1.612s.637-1.613 1.438-1.613c.807 0 1.451.73 1.438 1.613 0 .888-.631 1.612-1.438 1.612',
  },
  {
    name: 'LinkedIn',
    href: 'https://www.linkedin.com/company/rhesis-ai',
    viewBox: '0 0 24 24',
    path: 'M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z',
  },
  {
    name: 'X',
    href: 'https://x.com/rhesisai',
    viewBox: '0 0 24 24',
    path: 'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z',
  },
  {
    name: 'YouTube',
    href: 'https://www.youtube.com/@rhesis-ai',
    viewBox: '0 0 24 24',
    path: 'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z',
  },
]

export const Footer = () => {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="rhesis-footer">
      <div className="rhesis-footer__inner">
        <div className="rhesis-footer__top">
          <div className="rhesis-footer__brand">
            <a className="rhesis-footer__logo" href="/docs" aria-label="Rhesis AI">
              <img src="/logo/rhesis-mark.svg" alt="" width={56} height={37} loading="lazy" />
              <span>Rhesis AI</span>
            </a>
            <p className="rhesis-footer__tagline">
              Get the knowledge you need to develop your agents.
            </p>
            <div className="rhesis-footer__badges">
              <FooterOriginBadge />
              {/*
                The BMFTR mark is dark artwork on a transparent background, so it
                disappears into a dark footer. brightness(0) + invert flattens it
                to white.
              */}
              <img
                src="/logo/bmftr-light-mode.webp"
                alt="Funded by the German Federal Ministry of Research, Technology and Space"
                className="rhesis-footer__bmftr"
                width={163}
                height={98}
                loading="lazy"
              />
            </div>
          </div>

          <div className="rhesis-footer__columns">
            {footerColumns.map(column => (
              <div key={column.key} className="rhesis-footer__column">
                <h3>{column.title}</h3>
                <ul>
                  {column.links.map(link => (
                    <li key={link.name}>
                      <a
                        href={link.href}
                        target={link.external ? '_blank' : undefined}
                        rel={link.external ? 'noopener noreferrer' : undefined}
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

        <div className="rhesis-footer__bottom">
          <div className="rhesis-footer__bottom-left">
            <p>© {currentYear} Rhesis AI GmbH. Made in Potsdam, Germany.</p>
            <div className="rhesis-footer__legal">
              {legalLinks.map(link => (
                <a key={link.name} href={link.href} target="_blank" rel="noopener noreferrer">
                  {link.name}
                </a>
              ))}
            </div>
          </div>
          <div className="rhesis-footer__socials">
            {socialLinks.map(link => (
              <a
                key={link.name}
                href={link.href}
                aria-label={link.name}
                target="_blank"
                rel="noopener noreferrer"
              >
                <svg aria-hidden="true" fill="currentColor" viewBox={link.viewBox}>
                  <path d={link.path} />
                </svg>
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer
