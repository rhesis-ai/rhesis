import ThemeAwareLogo from './components/ThemeAwareLogo'
import Footer from './components/Footer'

export default {
  // Logo and branding
  logo: <ThemeAwareLogo />,

  // Color configuration - optimized for dark mode readability
  primaryHue: 200,
  primarySaturation: 100,

  // Navigation configuration
  navbar: {
    extraContent: null,
  },

  // Sidebar configuration
  sidebar: {
    titleComponent({ title, type }) {
      if (type === 'separator') {
        return <span className="cursor-default">{title}</span>
      }
      return <>{title}</>
    },
    defaultMenuCollapseLevel: 1,
    autoCollapse: true,
    toggleButton: true,
  },

  // Table of contents
  toc: {
    extraContent: null,
    float: true,
    title: 'On This Page',
  },

  // Search configuration
  search: {
    placeholder: 'Search documentation...',
    loading: 'Loading...',
    emptyResult: 'No results found.',
  },

  // Project links
  project: {
    link: 'https://github.com/rhesis-ai/rhesis',
    icon: (
      <svg style={{ width: 24, height: 24 }} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.374 0 0 5.373 0 12 0 17.302 3.438 21.8 8.207 23.387c.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
      </svg>
    ),
  },

  // Chat/Discord link
  chat: {
    link: 'https://discord.rhesis.ai',
    icon: (
      <svg style={{ width: 24, height: 24 }} viewBox="0 0 24 24" fill="currentColor">
        <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
      </svg>
    ),
  },

  // Repository configuration
  docsRepositoryBase: 'https://github.com/rhesis-ai/rhesis/tree/main/apps/documentation',

  // Edit link - disabled since pages are not editable
  editLink: null,

  // Feedback link
  feedback: {
    content: 'Any question or feedback? Contact us',
    labels: 'feedback',
    link: 'https://www.rhesis.ai/talk-to-us',
  },

  // Footer configuration
  footer: {
    text: <Footer />,
  },

  // Theme configuration
  darkMode: true,
  nextThemes: {
    defaultTheme: 'system',
  },

  // Typography and styling
  useNextSeoProps() {
    return {
      titleTemplate: '%s – Rhesis Documentation',
    }
  },

  // Head configuration
  head: (
    <>
      <meta key="viewport" name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta
        key="description"
        name="description"
        content="Rhesis: AI-powered testing and evaluation platform"
      />
      <meta
        key="og:description"
        name="og:description"
        content="Rhesis: AI-powered testing and evaluation platform"
      />
      <meta key="twitter:card" name="twitter:card" content="summary_large_image" />
      <meta key="twitter:image" name="twitter:image" content="/logo/rhesis-logo-website.png" />
      <meta key="twitter:site:domain" name="twitter:site:domain" content="docs.rhesis.ai" />
      <meta key="twitter:url" name="twitter:url" content="https://docs.rhesis.ai" />
      <meta key="og:image" name="og:image" content="/logo/rhesis-logo-website.png" />
      <meta
        key="apple-mobile-web-app-title"
        name="apple-mobile-web-app-title"
        content="Rhesis Docs"
      />
      <link
        key="favicon-light"
        rel="icon"
        type="image/svg+xml"
        href="/logo/rhesis-logo-favicon.svg"
        id="favicon-light"
      />
      <link
        key="favicon-dark"
        rel="icon"
        type="image/svg+xml"
        href="/logo/rhesis-logo-favicon-white.svg"
        id="favicon-dark"
        media="(prefers-color-scheme: dark)"
      />
      <script
        key="favicon-script"
        dangerouslySetInnerHTML={{
          __html: `
          (function() {
            function updateFavicon() {
              const isDark = document.documentElement.classList.contains('dark') ||
                           (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
              const lightFavicon = document.getElementById('favicon-light');
              const darkFavicon = document.getElementById('favicon-dark');

              if (isDark) {
                if (lightFavicon) lightFavicon.remove();
                if (!document.getElementById('favicon-dark')) {
                  const link = document.createElement('link');
                  link.id = 'favicon-dark';
                  link.rel = 'icon';
                  link.type = 'image/svg+xml';
                  link.href = '/logo/rhesis-logo-favicon-white.svg';
                  document.head.appendChild(link);
                }
              } else {
                if (darkFavicon) darkFavicon.remove();
                if (!document.getElementById('favicon-light')) {
                  const link = document.createElement('link');
                  link.id = 'favicon-light';
                  link.rel = 'icon';
                  link.type = 'image/svg+xml';
                  link.href = '/logo/rhesis-logo-favicon.svg';
                  document.head.appendChild(link);
                }
              }
            }

            // Update on load
            updateFavicon();

            // Watch for theme changes
            const observer = new MutationObserver(updateFavicon);
            observer.observe(document.documentElement, {
              attributes: true,
              attributeFilter: ['class']
            });

            // Watch for system theme changes
            if (window.matchMedia) {
              window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateFavicon);
            }
          })();
        `,
        }}
      />
    </>
  ),

  // Banner configuration
  banner: {
    dismissible: true,
    key: 'star-banner-2025',
  },

  // Git timestamp
  gitTimestamp: ({ timestamp }) => <>Last updated on {timestamp.toDateString()}</>,
}
