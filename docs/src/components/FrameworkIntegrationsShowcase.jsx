'use client'

import React from 'react'

/**
 * Dark “framework grid” for third-party tools Rhesis connects to.
 *
 * Logo sources:
 * - Most SVGs: Simple Icons (MIT) — https://simpleicons.org/ (CDN SVGs include brand fill)
 * - OpenAI / Azure: Simple Icons v11 SVGs (hex fills added in-repo; newer CDN omits some slugs)
 * - Cohere, Groq, Together AI, LiteLLM logo: BerriAI/litellm UI assets (dashboard `public/assets/logos`)
 * - DeepEval: `deepeval-logo.svg` from confident-ai/deepeval (`docs/static/icons/deepeval-logo.svg`)
 * - Ragas: project docs on GitHub (see file header in repo history)
 * - Polyphemus: `polyphemus-logo-favicon-transparent.svg` from apps/frontend/public/logos
 */

/**
 * Light tile behind logos so dark glyphs (e.g. black Simple Icons) stay visible.
 * Colors come from `globals.css` (`--integration-icon-well-*`). Not used for the white Rhesis favicon (`kind: 'rhesis'`).
 */
function IconWell({ wide, children }) {
  const cls = wide
    ? 'integration-icon-well integration-icon-well--wide'
    : 'integration-icon-well integration-icon-well--square'
  return <div className={cls}>{children}</div>
}

/** WebSocket registration + remote test runs — see /sdk/connector and /tracing (How It Works). */
const CONNECTOR_ITEM = {
  name: 'SDK Connector',
  href: '/sdk/connector',
  src: '/logo/rhesis-logo-favicon-white.svg',
  kind: 'rhesis',
}

const FRAMEWORK_TRACING_ITEMS = [
  {
    name: 'LangChain',
    href: '/docs/tracing/auto-instrumentation#langchain',
    src: '/integrations/langchain.svg',
    kind: 'simpleIcon',
  },
  {
    name: 'LangGraph',
    href: '/docs/tracing/auto-instrumentation#langgraph',
    src: '/integrations/langgraph.svg',
    kind: 'simpleIcon',
  },
]

/** LangChain, LangGraph, and SDK Connector — single Observability section on /docs/integrations */
const OBSERVABILITY_GRID_ITEMS = [...FRAMEWORK_TRACING_ITEMS, CONNECTOR_ITEM]

/** MCP server providers — sections on /docs/mcp */
const MCP_ITEMS = [
  {
    name: 'Notion',
    href: '/docs/mcp#notion',
    src: '/integrations/providers/notion.svg',
    kind: 'simpleIcon',
  },
  {
    name: 'GitHub',
    href: '/docs/mcp#github',
    src: '/integrations/providers/github.svg',
    kind: 'simpleIcon',
  },
  {
    name: 'Jira',
    href: '/docs/mcp#jira-or-confluence',
    src: '/integrations/providers/jira.svg',
    kind: 'simpleIcon',
  },
  {
    name: 'Confluence',
    href: '/docs/mcp#jira-or-confluence',
    src: '/integrations/providers/confluence.svg',
    kind: 'simpleIcon',
  },
]

const EVAL_ITEMS = [
  {
    name: 'DeepEval',
    href: '/docs/frameworks#deepeval',
    src: '/integrations/deepeval-logo.svg',
    kind: 'deepeval',
  },
  {
    name: 'Ragas',
    href: '/docs/frameworks#ragas',
    src: '/integrations/ragas-logo.png',
    kind: 'ragas',
  },
  {
    name: 'Garak',
    href: '/docs/frameworks#garak',
    src: '/integrations/nvidia.svg',
    kind: 'brand',
  },
]

/** Matches “Supported Providers” on /docs/models — icons from Simple Icons or GitHub org avatars. */
const MODEL_PROVIDERS = [
  { name: 'Anthropic', src: '/integrations/providers/anthropic.svg', kind: 'simpleIcon' },
  {
    name: 'Azure AI Studio',
    src: '/integrations/providers/microsoftazure.svg',
    kind: 'simpleIcon',
  },
  { name: 'Azure OpenAI', src: '/integrations/providers/microsoftazure.svg', kind: 'simpleIcon' },
  { name: 'Cohere', src: '/integrations/providers/cohere.svg', kind: 'simpleIcon' },
  { name: 'Google', src: '/integrations/providers/google.svg', kind: 'simpleIcon' },
  { name: 'Groq', src: '/integrations/providers/groq.svg', kind: 'simpleIcon' },
  { name: 'LiteLLM Proxy', src: '/integrations/providers/litellm_logo.jpg', kind: 'brand' },
  { name: 'Meta', src: '/integrations/providers/meta.svg', kind: 'simpleIcon' },
  { name: 'Mistral', src: '/integrations/providers/mistralai.svg', kind: 'simpleIcon' },
  { name: 'Ollama', src: '/integrations/providers/ollama.svg', kind: 'simpleIcon' },
  { name: 'OpenAI', src: '/integrations/providers/openai.svg', kind: 'simpleIcon' },
  { name: 'Perplexity', src: '/integrations/providers/perplexity.svg', kind: 'simpleIcon' },
  {
    name: 'Polyphemus',
    src: '/integrations/providers/polyphemus.svg',
    kind: 'simpleIcon',
  },
  { name: 'Replicate', src: '/integrations/providers/replicate.svg', kind: 'simpleIcon' },
  { name: 'Together AI', src: '/integrations/providers/together.svg', kind: 'simpleIcon' },
]

function LogoBox({ item }) {
  if (item.kind === 'deepeval') {
    return (
      <IconWell>
        <img
          src={item.src}
          alt=""
          width={32}
          height={32}
          style={{ width: '32px', height: '32px', objectFit: 'contain' }}
        />
      </IconWell>
    )
  }

  if (item.kind === 'ragas') {
    return (
      <IconWell>
        <img
          src={item.src}
          alt=""
          width={32}
          height={32}
          style={{ width: '32px', height: '32px', objectFit: 'contain' }}
        />
      </IconWell>
    )
  }

  if (item.kind === 'avatar') {
    return (
      <div
        style={{
          width: '40px',
          height: '40px',
          flexShrink: 0,
          borderRadius: '50%',
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.12)',
        }}
      >
        <img
          src={item.src}
          alt=""
          width={40}
          height={40}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>
    )
  }

  if (item.kind === 'rhesis') {
    return (
      <div
        style={{
          width: '40px',
          height: '40px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <img
          src={item.src}
          alt=""
          width={32}
          height={32}
          style={{ width: '32px', height: '32px', objectFit: 'contain' }}
        />
      </div>
    )
  }

  return (
    <IconWell>
      <img
        src={item.src}
        alt=""
        width={30}
        height={30}
        style={{
          width: '30px',
          height: '30px',
          objectFit: 'contain',
        }}
      />
    </IconWell>
  )
}

function GridCard({ item }) {
  return (
    <a
      className="integration-showcase-card"
      href={item.href}
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        padding: '1rem 1.25rem',
        borderRadius: '12px',
        border: '1px solid var(--integration-showcase-card-border)',
        background: 'var(--integration-showcase-card-bg)',
        boxShadow: 'var(--integration-showcase-card-shadow)',
        textDecoration: 'none',
        color: 'var(--integration-showcase-name)',
      }}
    >
      <span
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: 0,
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0, 0, 0, 0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        {item.name}
      </span>
      <LogoBox item={item} />
      <span
        style={{
          fontWeight: 600,
          fontSize: '0.9375rem',
          fontFamily: 'Sora, sans-serif',
          flex: 1,
          minWidth: 0,
        }}
      >
        {item.name}
      </span>
      <span
        aria-hidden
        style={{
          color: 'var(--integration-showcase-muted)',
          fontSize: '1rem',
          lineHeight: 1,
        }}
      >
        ↗
      </span>
    </a>
  )
}

function ProviderChip({ item }) {
  return (
    <div
      title={item.name}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.75rem 0.5rem',
        borderRadius: '10px',
        border: '1px solid var(--integration-showcase-chip-border)',
        background: 'var(--integration-showcase-chip-bg)',
        textAlign: 'center',
        minWidth: 0,
      }}
    >
      <LogoBox item={item} />
      <span
        style={{
          fontSize: '0.7rem',
          fontWeight: 600,
          color: 'var(--integration-showcase-chip-name)',
          lineHeight: 1.25,
          fontFamily: 'Be Vietnam Pro, sans-serif',
          maxWidth: '100%',
        }}
      >
        {item.name}
      </span>
    </div>
  )
}

export function McpSection() {
  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <p
        style={{
          margin: '0 0 1.25rem 0',
          fontSize: '0.9375rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '42rem',
          lineHeight: 1.55,
        }}
      >
        Connect MCP servers so Rhesis can use external tools during workflows. See the{' '}
        <a href="/docs/mcp" style={{ color: 'var(--integration-showcase-link)', fontWeight: 600 }}>
          MCP
        </a>{' '}
        guide for setup.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {MCP_ITEMS.map(item => (
          <GridCard key={item.name + item.href} item={item} />
        ))}
      </div>
    </section>
  )
}

export function ModelProvidersSection() {
  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <p
        style={{
          margin: '0 0 1.25rem 0',
          fontSize: '0.9375rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '44rem',
          lineHeight: 1.55,
        }}
      >
        Supported LLM backends (see also{' '}
        <a
          href="/docs/integrations/llm-providers"
          style={{ color: 'var(--integration-showcase-link)' }}
        >
          LLM providers
        </a>
        ) you can configure under{' '}
        <a
          href="/docs/models"
          style={{ color: 'var(--integration-showcase-link)', fontWeight: 600 }}
        >
          Models
        </a>
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(112px, 1fr))',
          gap: '0.65rem',
        }}
      >
        {MODEL_PROVIDERS.map(p => (
          <ProviderChip key={p.name} item={p} />
        ))}
      </div>
    </section>
  )
}

export function ConnectorSection() {
  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <p
        style={{
          margin: '0 0 1.25rem 0',
          fontSize: '0.9375rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '44rem',
          lineHeight: 1.55,
        }}
      >
        Register{' '}
        <code style={{ fontSize: '0.88em', color: 'var(--integration-showcase-code)' }}>
          @endpoint
        </code>{' '}
        functions so Rhesis discovers your app, lists callable endpoints, and runs tests over{' '}
        <strong style={{ color: 'var(--integration-showcase-strong)', fontWeight: 600 }}>
          WebSocket
        </strong>
        . See the{' '}
        <a
          href="/sdk/connector"
          style={{ color: 'var(--integration-showcase-link)', fontWeight: 600 }}
        >
          Connector
        </a>{' '}
        guide for setup.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '0.75rem',
        }}
      >
        <GridCard item={CONNECTOR_ITEM} />
      </div>
    </section>
  )
}

/** Tracing, auto-instrumentation, connector — see /docs/tracing/auto-instrumentation, /sdk/connector */
export function ObservabilitySection() {
  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <p
        style={{
          margin: '0 0 1.25rem 0',
          fontSize: '0.9375rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '44rem',
          lineHeight: 1.55,
        }}
      >
        <strong style={{ color: 'var(--integration-showcase-strong)', fontWeight: 600 }}>
          Rhesis
        </strong>{' '}
        provides observability via OpenTelemetry-based tracing.{' '}
        <a
          href="/docs/tracing/auto-instrumentation"
          style={{ color: 'var(--integration-showcase-link)', fontWeight: 600 }}
        >
          Auto-instrumentation
        </a>{' '}
        works out of the box for LangChain and LangGraph; connect any Python app using the{' '}
        <a
          href="/sdk/connector"
          style={{ color: 'var(--integration-showcase-link)', fontWeight: 600 }}
        >
          Connector
        </a>{' '}
        with the{' '}
        <code style={{ fontSize: '0.88em', color: 'var(--integration-showcase-code)' }}>
          @endpoint
        </code>{' '}
        decorator.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {OBSERVABILITY_GRID_ITEMS.map(item => (
          <GridCard key={item.name + item.href} item={item} />
        ))}
      </div>
    </section>
  )
}

export function TracingSection() {
  return <ObservabilitySection />
}

export function EvaluationSection() {
  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <p
        style={{
          margin: '0 0 1.25rem 0',
          fontSize: '0.9375rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '42rem',
          lineHeight: 1.55,
        }}
      >
        Library-backed metrics (DeepEval, Ragas, Rhesis) and Garak probe imports with mapped metrics
        in Rhesis test suites.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {EVAL_ITEMS.map(item => (
          <GridCard key={item.name + item.href} item={item} />
        ))}
      </div>
    </section>
  )
}

/** Import tests (e.g. Garak) and metrics (DeepEval, Ragas, Rhesis) — see /docs/frameworks */
export function TestsSection() {
  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <p
        style={{
          margin: '0 0 1.25rem 0',
          fontSize: '0.9375rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '44rem',
          lineHeight: 1.55,
        }}
      >
        In addition to Rhesis metrics, you can use DeepEval, Ragas, and Garak metrics and import
        Garak test sets — see{' '}
        <a
          href="/docs/frameworks"
          style={{ color: 'var(--integration-showcase-link)', fontWeight: 600 }}
        >
          framework integrations
        </a>
        .
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {EVAL_ITEMS.map(item => (
          <GridCard key={item.name + item.href} item={item} />
        ))}
      </div>
    </section>
  )
}

export function IntegrationsHub() {
  return (
    <div className="not-prose framework-integrations-showcase" style={{ margin: '1.5rem 0 0' }}>
      <p
        style={{
          margin: '0 0 1.75rem 0',
          fontSize: '0.975rem',
          color: 'var(--integration-showcase-lede)',
          maxWidth: '44rem',
          lineHeight: 1.6,
        }}
      >
        A single place to see how Rhesis plugs into your environment: observability and remote test
        runs, evaluation-framework integrations, MCP servers, and LLM providers.
      </p>
      <ObservabilitySection />
      <TestsSection />
      <McpSection />
      <ModelProvidersSection />
    </div>
  )
}

export function FrameworkIntegrationsShowcase() {
  return <IntegrationsHub />
}

export default IntegrationsHub
