import type { MetaRecord } from "nextra";

const meta: MetaRecord = {
  index: "Overview",
  organizations: "Organizations & Team",
  "---": {
    type: "separator",
    title: "Requirements",
  },
  projects: "Projects",
  knowledge: "Knowledge",
  behaviors: "Behaviors",
  metrics: "Metrics",
  "---testing": {
    type: "separator",
    title: "Testing",
  },
  "tests-generation": "Generation",
  tests: "Tests",
  "test-sets": "Test Sets",
  "test-execution": "Test Execution",
  "---results": {
    type: "separator",
    title: "Results",
  },
  "results-overview": "Overview",
  "test-runs": "Test Runs",
  tasks: "Tasks",
  "---development": {
    type: "separator",
    title: "Development",
  },
  endpoints: "Endpoints",
  models: "Platform Models",
  mcp: "MCP",
  "api-tokens": "API Tokens",
  // Hidden old pages (kept for backwards compatibility with existing links)
  integrations: {
    display: "hidden",
  },
  "test-results": {
    display: "hidden",
  },
  "test-sets-runs": {
    display: "hidden",
  },
};

export default meta;
