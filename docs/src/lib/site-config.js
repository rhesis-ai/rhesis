/**
 * Site-wide SEO configuration
 * Central place for all SEO-related constants and metadata
 */

export const siteConfig = {
  // Base site information
  siteUrl: 'https://docs.rhesis.ai',
  siteName: 'Rhesis Documentation',
  siteDescription:
    'Structured feedback and evals for AI agents. Connect the agent you are building, share it with your team, and turn their feedback into tests and metrics that run on every change.',

  // Social media
  twitterHandle: '@rhesis_ai',
  twitterSite: '@rhesis_ai',

  // Default images for social sharing
  defaultImage: '/GH_Short_Demo.png',
  defaultImageAlt: 'Rhesis - structured feedback and evals for AI agents',

  // Organization information
  organization: {
    name: 'Rhesis',
    url: 'https://www.rhesis.ai',
    logo: 'https://docs.rhesis.ai/logo/rhesis-Logo-rgb-main-logo.png',
    description: 'Structured feedback and evals for AI agents',
  },

  // Author information
  author: {
    name: 'Rhesis Team',
    url: 'https://www.rhesis.ai',
  },

  // Additional metadata
  keywords: [
    'AI agent evaluation',
    'LLM evaluation',
    'structured feedback',
    'domain expert review',
    'agent testing',
    'collaborative testing',
    'test generation',
    'LLM as a judge',
    'AI metrics',
  ],

  // Theme and appearance
  themeColor: '#111827',
  backgroundColor: '#ffffff',

  // Locale
  locale: 'en_US',
  language: 'en',
}

export default siteConfig
