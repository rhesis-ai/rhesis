import ThemeAwareLogo from './components/ThemeAwareLogo'

export default {
  logo: <ThemeAwareLogo />,
  project: {
    link: 'https://github.com/rhesis-ai/rhesis',
  },
  docsRepositoryBase: 'https://github.com/rhesis-ai/rhesis',
  footer: {
    text: '© 2025 Rhesis AI GmbH. Made in Germany.',
  },
  head: (
    <>
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta property="og:title" content="Rhesis Documentation" />
      <meta property="og:description" content="AI-powered testing and evaluation platform" />
    </>
  ),
  useNextSeoProps() {
    return {
      titleTemplate: '%s – Rhesis'
    }
  },
  primaryHue: 210,
  primarySaturation: 100,
  toc: {
    float: true,
    title: 'On This Page',
  },
  sidebar: {
    titleComponent: ({ title, type }) => {
      if (type === 'separator') {
        return <span className="cursor-default">{title}</span>
      }
      return <>{title}</>
    },
    defaultMenuCollapseLevel: 1,
    toggleButton: true,
  },
  feedback: {
    content: 'Question? Give us feedback →',
    labels: 'feedback'
  },
  editLink: {
    text: 'Edit this page on GitHub →'
  },
  banner: {
    key: 'rhesis-docs',
    text: 'Welcome to Rhesis Documentation 🚀'
  }
}
