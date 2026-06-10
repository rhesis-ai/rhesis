'use client'

import React from 'react'
import QuizOutlined from '@mui/icons-material/QuizOutlined'
import ViewListOutlined from '@mui/icons-material/ViewListOutlined'
import RuleOutlined from '@mui/icons-material/RuleOutlined'
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined'
import HubOutlined from '@mui/icons-material/HubOutlined'
import CloudOutlined from '@mui/icons-material/CloudOutlined'
import IntegrationInstructionsOutlined from '@mui/icons-material/IntegrationInstructionsOutlined'
import PlayCircleOutlined from '@mui/icons-material/PlayCircleOutlined'
import BarChartOutlined from '@mui/icons-material/BarChartOutlined'
import { InfoCard } from './InfoCard'

const ZoneHeader = ({ title, subtitle }) => (
  <div style={{ marginBottom: '0.75rem' }}>
    <div
      style={{
        fontSize: '0.75rem',
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--accent-color, #FD6E12)',
        fontFamily: 'Sora, sans-serif',
      }}
    >
      {title}
    </div>
    {subtitle ? (
      <div
        style={{
          fontSize: '0.8125rem',
          color: 'var(--text-secondary, #6B7280)',
          marginTop: '0.15rem',
        }}
      >
        {subtitle}
      </div>
    ) : null}
  </div>
)

const SubsectionLabel = ({ children }) => (
  <div
    style={{
      fontSize: '0.8125rem',
      fontWeight: 600,
      color: 'var(--text-primary, #3D3D3D)',
      margin: '0.75rem 0 0.5rem',
      fontFamily: 'Sora, sans-serif',
    }}
  >
    {children}
  </div>
)

const FlowArrow = ({ direction = 'right', fullWidth = false }) => (
  <div
    aria-hidden="true"
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--text-tertiary, #9CA3AF)',
      fontSize: direction === 'down' ? '2rem' : '1.5rem',
      padding: direction === 'down' ? '0.25rem 0' : '0 0.5rem',
      flexShrink: 0,
      width: fullWidth ? '100%' : 'auto',
    }}
  >
    {direction === 'down' ? '↓' : '→'}
  </div>
)

const cardGridStyle = {
  display: 'grid',
  gridTemplateColumns: '1fr',
  gap: '0.5rem',
}

export const PlatformStructureMap = () => {
  const zoneStyle = {
    padding: '0.75rem',
    border: '1px solid var(--border-color, #e5e7eb)',
    borderRadius: '0.75rem',
    backgroundColor: 'var(--nextra-bg, #fafafa)',
  }

  const columnStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  }

  const twoColStyle = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '0.75rem',
  }

  return (
    <div
      style={{ margin: '1rem 0', maxWidth: '900px' }}
      className="not-prose rhesis-platform-structure"
    >
      <div style={columnStyle}>
        {/* Setup zone */}
        <div style={zoneStyle}>
          <ZoneHeader title="Setup" subtitle="Configure before you run" />
          <div style={twoColStyle}>
            <div>
              <SubsectionLabel>What to test</SubsectionLabel>
              <div style={cardGridStyle}>
                <InfoCard
                  icon={QuizOutlined}
                  title="Test"
                  description="One prompt or conversation goal, tagged with a behavior."
                  link="/docs/tests-generation"
                />
                <InfoCard
                  icon={ViewListOutlined}
                  title="Test set"
                  description="Batch of tests for a run. A test can belong to many sets."
                  link="/docs/test-sets"
                />
              </div>
            </div>
            <div>
              <SubsectionLabel>How to measure</SubsectionLabel>
              <div style={cardGridStyle}>
                <InfoCard
                  icon={RuleOutlined}
                  title="Behavior"
                  description="What good looks like. Defaults: Reliability, Robustness, Compliance."
                  link="/docs/behaviors"
                />
                <InfoCard
                  icon={AnalyticsOutlined}
                  title="Metric"
                  description="Judge assigned to behaviors. Pass/fail, score, and reasoning."
                  link="/docs/metrics"
                />
              </div>
            </div>
          </div>
        </div>

        <FlowArrow direction="down" fullWidth />

        {/* Your application zone */}
        <div style={zoneStyle}>
          <ZoneHeader title="Your application" subtitle="System under test" />
          <InfoCard
            icon={HubOutlined}
            title="Endpoint"
            description="How Rhesis reaches your app. Sends input, receives output for evaluation."
            link="/docs/endpoints"
          />
          <div
            style={{
              marginTop: '0.75rem',
              paddingTop: '0.75rem',
              borderTop: '1px solid var(--border-color, #e5e7eb)',
            }}
          >
            <SubsectionLabel style={{ marginTop: 0 }}>Connection options</SubsectionLabel>
            <div style={{ ...cardGridStyle, gridTemplateColumns: '1fr 1fr' }}>
              <InfoCard
                icon={CloudOutlined}
                title="REST API"
                description="HTTP endpoint with URL and UI mapping."
                link="/docs/endpoints"
              />
              <InfoCard
                icon={IntegrationInstructionsOutlined}
                title="SDK Connector"
                description="@endpoint on your function, invoked over WebSocket."
                link="/sdk/connector"
              />
            </div>
          </div>
        </div>

        <FlowArrow direction="down" fullWidth />

        {/* Results zone */}
        <div style={zoneStyle}>
          <ZoneHeader title="Results" subtitle="What you get after a run" />
          <div style={twoColStyle}>
            <InfoCard
              icon={PlayCircleOutlined}
              title="Test run"
              description="One execution of a test set against an endpoint. Full snapshot."
              link="/docs/test-runs"
            />
            <InfoCard
              icon={BarChartOutlined}
              title="Results overview"
              description="Dashboard across runs: trends, pass rates by behavior."
              link="/docs/results-overview"
            />
          </div>
        </div>
      </div>

      <p
        style={{
          margin: '0.75rem 0 0',
          fontSize: '0.8125rem',
          color: 'var(--text-secondary, #6B7280)',
          lineHeight: 1.5,
        }}
      >
        Solid flow: test set → endpoint → test run. Metrics score each test result after the
        response returns.
      </p>
    </div>
  )
}

export default PlatformStructureMap
