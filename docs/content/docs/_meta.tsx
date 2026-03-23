import type { MetaRecord } from 'nextra'

const iconProps = {
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'currentColor',
  width: 18,
  height: 18,
  style: { verticalAlign: 'middle', marginRight: 6, flexShrink: 0 } as const,
}

const RocketLaunch = () => (
  <svg {...iconProps}>
    <path d="M6 15c-.83 0-1.58.34-2.12.88C2.7 17.06 2 22 2 22s4.94-.7 6.12-1.88c.54-.54.88-1.29.88-2.12 0-1.66-1.34-3-3-3m.71 3.71c-.28.28-2.17.76-2.17.76s.47-1.88.76-2.17c.17-.19.42-.3.7-.3.55 0 1 .45 1 1 0 .28-.11.53-.29.71m10.71-5.06c6.36-6.36 4.24-11.31 4.24-11.31S16.71.22 10.35 6.58l-2.49-.5c-.65-.13-1.33.08-1.81.55L2 10.69l5 2.14L11.17 17l2.14 5 4.05-4.05c.47-.47.68-1.15.55-1.81zM7.41 10.83l-1.91-.82 1.97-1.97 1.44.29c-.57.83-1.08 1.7-1.5 2.5m6.58 7.67-.82-1.91c.8-.42 1.67-.93 2.49-1.5l.29 1.44zM16 12.24c-1.32 1.32-3.38 2.4-4.04 2.73l-2.93-2.93c.32-.65 1.4-2.71 2.73-4.04 4.68-4.68 8.23-3.99 8.23-3.99s.69 3.55-3.99 8.23M15 11c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2" />
  </svg>
)

const Lightbulb = () => (
  <svg {...iconProps}>
    <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7m2.85 11.1-.85.6V16h-4v-2.3l-.85-.6C7.8 12.16 7 10.63 7 9c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.63-.8 3.16-2.15 4.1" />
  </svg>
)

const Explore = () => (
  <svg {...iconProps}>
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2m0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8m-5.5-2.5 7.51-3.49L17.5 6.5 9.99 9.99zm5.5-6.6c.61 0 1.1.49 1.1 1.1s-.49 1.1-1.1 1.1-1.1-.49-1.1-1.1.49-1.1 1.1-1.1" />
  </svg>
)

const EditNote = () => (
  <svg {...iconProps}>
    <path d="M3 10h11v2H3zm0-2h11V6H3zm0 8h7v-2H3zm15.01-3.13.71-.71c.39-.39 1.02-.39 1.41 0l.71.71c.39.39.39 1.02 0 1.41l-.71.71zm-.71.71-5.3 5.3V21h2.12l5.3-5.3z" />
  </svg>
)

const PlayCircle = () => (
  <svg {...iconProps}>
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2m0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8m-2.5-3.5 7-4.5-7-4.5z" />
  </svg>
)

const Assessment = () => (
  <svg {...iconProps}>
    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2m0 16H5V5h14zM7 10h2v7H7zm4-3h2v10h-2zm4 6h2v4h-2z" />
  </svg>
)

const Settings = () => (
  <svg {...iconProps}>
    <path d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.09-.16-.26-.25-.44-.25-.06 0-.12.01-.17.03l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1q-.09-.03-.18-.03c-.17 0-.34.09-.43.25l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.09.16.26.25.44.25.06 0 .12-.01.17-.03l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1q.09.03.18.03c.17 0 .34-.09.43-.25l2-3.46c.12-.22.07-.49-.12-.64zm-1.98-1.71c.04.31.05.52.05.73s-.02.43-.05.73l-.14 1.13.89.7 1.08.84-.7 1.21-1.27-.51-1.04-.42-.9.68c-.43.32-.84.56-1.25.73l-1.06.43-.16 1.13-.2 1.35h-1.4l-.19-1.35-.16-1.13-1.06-.43c-.43-.18-.83-.41-1.23-.71l-.91-.7-1.06.43-1.27.51-.7-1.21 1.08-.84.89-.7-.14-1.13c-.03-.31-.05-.54-.05-.74s.02-.43.05-.73l.14-1.13-.89-.7-1.08-.84.7-1.21 1.27.51 1.04.42.9-.68c.43-.32.84-.56 1.25-.73l1.06-.43.16-1.13.2-1.35h1.39l.19 1.35.16 1.13 1.06.43c.43.18.83.41 1.23.71l.91.7 1.06-.43 1.27-.51.7 1.21-1.07.85-.89.7zM12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4m0 6c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2" />
  </svg>
)

const meta: MetaRecord = {
  index: 'Welcome',
  'getting-started': {
    title: (
      <span className="sidebar-icon-label">
        <RocketLaunch />
        Getting Started
      </span>
    ),
  },
  concepts: {
    title: (
      <span className="sidebar-icon-label">
        <Lightbulb />
        Core Concepts
      </span>
    ),
  },
  'product-tour': {
    title: (
      <span className="sidebar-icon-label">
        <Explore />
        Product Tour
      </span>
    ),
  },

  '---define': {
    type: 'separator',
    title: (
      <span className="sidebar-icon-label">
        <EditNote />
        Define
      </span>
    ),
  },
  projects: 'Projects',
  knowledge: 'Knowledge',
  expectations: 'Expectations',
  behaviors: 'Behaviors',
  metrics: 'Metrics',
  'tests-generation': 'Test Generation',
  tests: 'Tests',
  'test-sets': 'Test Sets',
  playground: 'Playground',

  '---run': {
    type: 'separator',
    title: (
      <span className="sidebar-icon-label">
        <PlayCircle />
        Run
      </span>
    ),
  },
  'test-execution': 'Test Execution',
  'test-runs': 'Test Runs',
  'conversation-simulation': 'Conversation Simulation',
  'adversarial-testing': 'Adversarial Testing',
  'multimodal-testing': 'Multi-modal Testing',

  '---review': {
    type: 'separator',
    title: (
      <span className="sidebar-icon-label">
        <Assessment />
        Review
      </span>
    ),
  },
  'results-overview': 'Results Overview',
  tracing: 'Tracing',
  'test-reviews': 'Test Reviews',
  tasks: 'Tasks',

  '---setup': {
    type: 'separator',
    title: (
      <span className="sidebar-icon-label">
        <Settings />
        Setup
      </span>
    ),
  },
  organizations: 'Organizations & Team',
  endpoints: 'Endpoints',
  models: 'Models',
  mcp: 'MCP',
  'api-tokens': 'API Tokens',
  deployment: 'Deployment',
  frameworks: 'Frameworks',

  '---bottom': {
    type: 'separator',
  },
  acknowledgments: 'Acknowledgments',

  integrations: { display: 'hidden' },
  'test-results': { display: 'hidden' },
  'test-sets-runs': { display: 'hidden' },
}

export default meta
