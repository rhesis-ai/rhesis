/**
 * Header text of the directory pages. Each page and its `loading.tsx` read the same
 * entry, so the header a click paints at once is the one the page keeps.
 * Detail pages use `title` and `href` as their first breadcrumb.
 */

export interface PageHeader {
  title: string;
  description: string;
  href: string;
}

export const PAGE_HEADERS = {
  annotations: {
    title: 'Annotations',
    description:
      'Browse human judgments on test results and traces across your project.',
    href: '/annotations',
  },
  endpoints: {
    title: 'Endpoints',
    description:
      'Connect the Rhesis platform to your application under test via endpoints to enable comprehensive testing and evaluation workflows.',
    href: '/endpoints',
  },
  experiments: {
    title: 'Experiments',
    description:
      'Experiments are named bundles of parameter values that can be pinned to test runs, ensuring reproducible and comparable executions across your project.',
    href: '/experiments',
  },
  insights: {
    title: 'Insights',
    description:
      'View pass rates by requirement, impact or parent requirement, broken down by metric and topic. Filter by time range or pick specific test runs in the filter drawer.',
    href: '/insights',
  },
  jobs: {
    title: 'Jobs',
    description:
      'Background work the platform is doing, and what it logged along the way.',
    href: '/jobs',
  },
  knowledge: {
    title: 'Knowledge',
    description:
      'Upload knowledge sources to use as context for test generation and evaluation workflows.',
    href: '/knowledge',
  },
  metrics: {
    title: 'Metrics',
    description:
      'Metrics are quantifiable measurements that evaluate requirements and determine if requirements are met.',
    href: '/metrics',
  },
  models: {
    title: 'Models',
    description:
      'Connect language models for test generation and language-model-as-judge evaluation. Set your defaults for generation, evaluation, and execution.',
    href: '/models',
  },
  playground: {
    title: 'Playground',
    description:
      'Chat with your endpoints interactively to test their responses and generate test cases from your conversations.',
    href: '/playground',
  },
  projects: {
    title: 'Projects',
    description:
      'Organize your AI applications by grouping endpoints, tests, and results into projects.',
    href: '/projects',
  },
  reports: {
    title: 'Reports',
    description:
      "Summaries of an endpoint's test runs, for a release or a review. Drafts stay live; published reports are frozen.",
    href: '/reports',
  },
  requirements: {
    title: 'Requirements',
    description:
      'Requirements are atomic expectations for your application, measured through one or more metrics to determine if requirements are met.',
    href: '/requirements',
  },
  tasks: {
    title: 'Tasks',
    description:
      'Track and manage work items linked to tests, endpoints, and comments across your organization.',
    href: '/tasks',
  },
  testRuns: {
    title: 'Test Runs',
    description:
      'Executions of your test sets against AI endpoints. Track status, results, and history of each run.',
    href: '/test-runs',
  },
  testSets: {
    title: 'Test Sets',
    description:
      'Curated collections of tests you can version, share, and execute against your AI endpoints.',
    href: '/test-sets',
  },
  tests: {
    title: 'Tests',
    description:
      'Individual test cases that evaluate your AI endpoints for quality, safety, and reliability.',
    href: '/tests',
  },
  tokens: {
    title: 'API Tokens',
    description:
      'Create API tokens to authenticate with the Rhesis SDK and programmatically manage your testing workflows from your code.',
    href: '/tokens',
  },
  tools: {
    title: 'Tools',
    description:
      'Connect tools and external services to import knowledge sources and enhance your evaluation workflows.',
    href: '/tools',
  },
  traces: {
    title: 'Traces',
    description:
      'OpenTelemetry traces from test runs and live endpoint traffic. Inspect spans, metrics, and annotations.',
    href: '/traces',
  },
} as const satisfies Record<string, PageHeader>;

/** Models also describes embedding models when they are enabled. */
const MODELS_DESCRIPTION_WITH_EMBEDDINGS =
  'Connect language models for test generation and language-model-as-judge evaluation, and embedding models for platform use. Set your defaults for generation, evaluation, and execution.';

export function modelsDescription(embeddingsEnabled: boolean): string {
  return embeddingsEnabled
    ? MODELS_DESCRIPTION_WITH_EMBEDDINGS
    : PAGE_HEADERS.models.description;
}

/** A directory page as the first breadcrumb of the pages under it. */
export function directoryCrumb(header: PageHeader): {
  label: string;
  href: string;
} {
  return { label: header.title, href: header.href };
}

export const MANUAL_TEST_WRITER_HEADER = {
  title: 'Manual Test Writer',
  description: 'Create test cases manually. One test case per row.',
} as const;

export const NEW_METRIC_CRUMB = 'New Metric';
