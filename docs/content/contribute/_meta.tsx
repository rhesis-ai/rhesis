import type { MetaRecord } from 'nextra'

const iconProps = {
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'currentColor',
  width: 18,
  height: 18,
  style: { verticalAlign: 'middle', marginRight: 6, flexShrink: 0 } as const,
}

const ArchitectureIcon = () => (
  <svg {...iconProps}>
    <path d="M3 3h8v8H3zm10 0h8v8h-8zM3 13h8v8H3zm14 0h-4v4h-4v4h8z" />
  </svg>
)

const ReferenceIcon = () => (
  <svg {...iconProps}>
    <path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2m0 18H6V4h2v8l2.5-1.5L13 12V4h5z" />
  </svg>
)

const meta: MetaRecord = {
  index: 'Overview',
  'development-setup': 'Development Setup',
  'coding-standards': 'Coding Standards',
  'managing-docs': 'Managing Documentation',

  '---architecture': {
    type: 'separator',
    title: (
      <span className="sidebar-icon-label">
        <ArchitectureIcon />
        Architecture
      </span>
    ),
  },
  frontend: 'Frontend',
  backend: 'Backend',
  worker: 'Worker',
  'tracing-system': 'Tracing System',
  polyphemus: 'Polyphemus',
  connector: 'Connector',

  '---reference': {
    type: 'separator',
    title: (
      <span className="sidebar-icon-label">
        <ReferenceIcon />
        Reference
      </span>
    ),
  },
  'environment-variables': 'Environment Variables',
  telemetry: 'Telemetry',
}

export default meta
