import type { MetaRecord } from 'nextra'

const iconProps = {
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'currentColor',
  width: 16,
  height: 16,
  style: { verticalAlign: 'middle', marginRight: 5, flexShrink: 0 } as const,
}

const DocsIcon = () => (
  <svg {...iconProps}>
    <path d="M19 2H6c-1.21 0-2 .79-2 2v14c0 1.21.79 2 2 2h1v2l4-2h8c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2m0 16H10l-3 1.5V18H6V4h13z" />
    <path d="M8 7h8v2H8zm0 3h8v2H8zm0 3h5v2H8z" />
  </svg>
)

const GuidesIcon = () => (
  <svg {...iconProps}>
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7m0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5S13.38 11.5 12 11.5" />
  </svg>
)

const SdkIcon = () => (
  <svg {...iconProps}>
    <path d="M9.4 16.6 4.8 12l4.6-4.6L8 6l-6 6 6 6zm5.2 0 4.6-4.6-4.6-4.6L16 6l6 6-6 6z" />
  </svg>
)

const GlossaryIcon = () => (
  <svg {...iconProps}>
    <path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2m-1 9H9V9h10zm-4 4H9v-2h6zm4-8H9V5h10z" />
  </svg>
)

const ChangelogIcon = () => (
  <svg {...iconProps}>
    <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2M12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8m.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" />
  </svg>
)

const ContributeIcon = () => (
  <svg {...iconProps}>
    <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3m-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3m0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5m8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5" />
  </svg>
)

const SdkReferenceIcon = () => (
  <svg {...iconProps}>
    <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3z" />
  </svg>
)

const meta: MetaRecord = {
  index: {
    type: 'page',
    display: 'hidden',
    theme: { layout: 'full' },
  },
  docs: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <DocsIcon />
        Docs
      </span>
    ),
  },
  guides: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <GuidesIcon />
        Guides
      </span>
    ),
  },
  sdk: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <SdkIcon />
        SDK
      </span>
    ),
  },
  glossary: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <GlossaryIcon />
        Glossary
      </span>
    ),
    theme: { sidebar: false },
  },
  changelog: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <ChangelogIcon />
        Changelog
      </span>
    ),
    theme: { sidebar: false },
  },
  contribute: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <ContributeIcon />
        Contribute
      </span>
    ),
  },
  sdk_reference: {
    type: 'page',
    title: (
      <span className="sidebar-icon-label">
        <SdkReferenceIcon />
        SDK Reference
      </span>
    ),
    href: 'https://rhesis-sdk.readthedocs.io/en/latest/',
  },
}

export default meta
