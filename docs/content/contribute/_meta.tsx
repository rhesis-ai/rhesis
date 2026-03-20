import type { MetaRecord } from 'nextra'

const meta: MetaRecord = {
  index: 'Overview',
  'development-setup': 'Development Setup',
  'coding-standards': 'Coding Standards',
  'managing-docs': 'Managing Documentation',

  '---architecture': {
    type: 'separator',
    title: '🏗️ Architecture',
  },
  frontend: 'Frontend',
  backend: 'Backend',
  worker: 'Worker',
  'tracing-system': 'Tracing System',
  polyphemus: 'Polyphemus',
  connector: 'Connector',

  '---reference': {
    type: 'separator',
    title: '📚 Reference',
  },
  'environment-variables': 'Environment Variables',
  telemetry: 'Telemetry',
}

export default meta
