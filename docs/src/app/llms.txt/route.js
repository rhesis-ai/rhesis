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
- Installation and setup: https://docs.rhesis.ai/docs/getting-started
- Core concepts: https://docs.rhesis.ai/docs/concepts
- Running locally: https://docs.rhesis.ai/docs/deployment/running-locally
- Self-hosting: https://docs.rhesis.ai/docs/deployment/self-hosting

### Platform
- Projects: https://docs.rhesis.ai/docs/projects
- Endpoints: https://docs.rhesis.ai/docs/endpoints
- Models: https://docs.rhesis.ai/docs/models
- Knowledge: https://docs.rhesis.ai/docs/knowledge
- Behaviors: https://docs.rhesis.ai/docs/behaviors
- Metrics: https://docs.rhesis.ai/docs/metrics
- Test Generation: https://docs.rhesis.ai/docs/tests-generation
- Tests: https://docs.rhesis.ai/docs/tests
- Test Sets: https://docs.rhesis.ai/docs/test-sets
- Test Runs: https://docs.rhesis.ai/docs/test-runs
- Tasks: https://docs.rhesis.ai/docs/tasks
- API Tokens: https://docs.rhesis.ai/docs/api-tokens
- MCP: https://docs.rhesis.ai/docs/mcp

### SDK
- Installation: https://docs.rhesis.ai/sdk/installation
- Entities: https://docs.rhesis.ai/sdk/entities
- Models: https://docs.rhesis.ai/sdk/models
- Synthesizers: https://docs.rhesis.ai/sdk/synthesizers
- Metrics: https://docs.rhesis.ai/sdk/metrics
- Connector: https://docs.rhesis.ai/sdk/connector

### Contribute
- Overview: https://docs.rhesis.ai/contribute
- Backend: https://docs.rhesis.ai/contribute/backend
- Frontend: https://docs.rhesis.ai/contribute/frontend
- Worker: https://docs.rhesis.ai/contribute/worker
- Connector: https://docs.rhesis.ai/contribute/connector
- Environment Variables: https://docs.rhesis.ai/contribute/environment-variables
- Development Setup: https://docs.rhesis.ai/contribute/development-setup

### Conversation Simulation
- Overview: https://docs.rhesis.ai/docs/conversation-simulation
- Getting Started: https://docs.rhesis.ai/docs/conversation-simulation/getting-started
- Examples: https://docs.rhesis.ai/docs/conversation-simulation/examples
- Configuration: https://docs.rhesis.ai/docs/conversation-simulation/configuration

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
- Contact: https://www.rhesis.ai/talk-to-us
`

  return new Response(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
