/**
 * llms.txt route handler
 * Provides a machine-readable file for LLMs to understand the site structure
 * See: https://llmstxt.org/
 */

export async function GET() {
  const content = `# Rhesis Documentation

> AI-powered testing and evaluation platform for Gen AI applications

## Overview

Rhesis is a collaborative testing platform that brings together developers, domain experts, and stakeholders to create comprehensive testing for Gen AI applications.

## Main Sections

### Getting Started
- Installation and setup: https://docs.rhesis.ai/getting-started
- Core concepts: https://docs.rhesis.ai/getting-started/concepts
- Running locally: https://docs.rhesis.ai/getting-started/running-locally
- Self-hosting: https://docs.rhesis.ai/getting-started/self-hosting

### Platform
- Projects: https://docs.rhesis.ai/platform/projects
- Endpoints: https://docs.rhesis.ai/platform/endpoints
- Models: https://docs.rhesis.ai/platform/models
- Knowledge: https://docs.rhesis.ai/platform/knowledge
- Behaviors: https://docs.rhesis.ai/platform/behaviors
- Metrics: https://docs.rhesis.ai/platform/metrics
- Test Generation: https://docs.rhesis.ai/platform/tests-generation
- Tests: https://docs.rhesis.ai/platform/tests
- Test Sets: https://docs.rhesis.ai/platform/test-sets
- Test Runs: https://docs.rhesis.ai/platform/test-runs
- Tasks: https://docs.rhesis.ai/platform/tasks
- API Tokens: https://docs.rhesis.ai/platform/api-tokens
- MCP: https://docs.rhesis.ai/platform/mcp

### SDK
- Installation: https://docs.rhesis.ai/sdk/installation
- Entities: https://docs.rhesis.ai/sdk/entities
- Models: https://docs.rhesis.ai/sdk/models
- Synthesizers: https://docs.rhesis.ai/sdk/synthesizers
- Metrics: https://docs.rhesis.ai/sdk/metrics
- Connector: https://docs.rhesis.ai/sdk/connector

### Development
- Backend: https://docs.rhesis.ai/development/backend
- Frontend: https://docs.rhesis.ai/development/frontend
- Worker: https://docs.rhesis.ai/development/worker
- Connector: https://docs.rhesis.ai/development/connector
- Environment Variables: https://docs.rhesis.ai/development/environment-variables
- Contributing: https://docs.rhesis.ai/development/contributing

### Penelope
- Overview: https://docs.rhesis.ai/penelope
- Getting Started: https://docs.rhesis.ai/penelope/getting-started
- Examples: https://docs.rhesis.ai/penelope/examples
- Configuration: https://docs.rhesis.ai/penelope/configuration

## Key Features

- **Collaborative Testing**: Bring together technical and non-technical stakeholders
- **Test Generation**: Automatically generate test cases using AI
- **LLM as Judge**: Evaluate responses using metrics powered by LLMs
- **SDK Integration**: Python SDK for programmatic access
- **Multi-turn Testing**: Support for conversational AI testing
- **Custom Metrics**: Define custom evaluation criteria
- **Knowledge Management**: Organize domain knowledge for test generation

## API Reference

Full SDK reference: https://rhesis-sdk.readthedocs.io/en/latest/

## Support

- GitHub: https://github.com/rhesis-ai/rhesis
- Discord: https://discord.rhesis.ai
- Website: https://www.rhesis.ai
- Contact: https://www.rhesis.ai/contact-us
`

  return new Response(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
