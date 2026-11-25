import { Capability } from '@/constants/capabilities';

/**
 * Header of the directory pages. Each page and its `loading.tsx` read the same
 * entry, so the header a click paints at once is the one the page keeps.
 * Detail pages use `title` and `href` as their first breadcrumb.
 */

/** What shows one header button: a capability, any of several, or null for
 *  a button everyone gets. */
export type ActionGate = string | readonly string[] | null;

export interface PageHeader {
  title: string;
  description: string;
  href: string;
  /** The buttons the page shows on arrival, in order (not the ones that only
   *  appear for a selection), so the loading header can draw one placeholder
   *  per button the user will get. Keep in step with the page's FabGroup. */
  actions: readonly ActionGate[];
}

export const PAGE_HEADERS = {
  annotations: {
    title: 'Annotations',
    description:
      'Browse human judgments on test results and traces across your project.',
    href: '/annotations',
    actions: [],
  },
  endpoints: {
    title: 'Endpoints',
    description:
      'Connect the Rhesis platform to your application under test via endpoints to enable comprehensive testing and evaluation workflows.',
    href: '/endpoints',
    actions: [Capability.Endpoint.CREATE],
  },
  experiments: {
    title: 'Experiments',
    description:
      'Experiments are named bundles of parameter values that can be pinned to test runs, ensuring reproducible and comparable executions across your project.',
    href: '/experiments',
    actions: [null, Capability.Experiment.CREATE],
  },
  insights: {
    title: 'Insights',
    description:
      'View pass rates by requirement, impact or parent requirement, broken down by metric and topic. Filter by time range or pick specific test runs in the filter drawer.',
    href: '/insights',
    actions: [Capability.Architect.CREATE, null],
  },
  jobs: {
    title: 'Jobs',
    description:
      'Background work the platform is doing, and what it logged along the way.',
    href: '/jobs',
    actions: [],
  },
  knowledge: {
    title: 'Knowledge',
    description:
      'Upload knowledge sources to use as context for test generation and evaluation workflows.',
    href: '/knowledge',
    actions: [Capability.Source.CREATE, Capability.Source.CREATE],
  },
  metrics: {
    title: 'Metrics',
    description:
      'Metrics are quantifiable measurements that evaluate requirements and determine if requirements are met.',
    href: '/metrics',
    actions: [Capability.Metric.CREATE],
  },
  models: {
    title: 'Models',
    description:
      'Connect language models for test generation and language-model-as-judge evaluation. Set your defaults for generation, evaluation, and execution.',
    href: '/models',
    actions: [Capability.Model.CREATE],
  },
  playground: {
    title: 'Playground',
    description:
      'Chat with your endpoints interactively to test their responses and generate test cases from your conversations.',
    href: '/playground',
    actions: [null, null],
  },
  projects: {
    title: 'Projects',
    description:
      'Organize your AI applications by grouping endpoints, tests, and results into projects.',
    href: '/projects',
    actions: [Capability.Project.CREATE],
  },
  reports: {
    title: 'Reports',
    description:
      "Summaries of an endpoint's test runs, for a release or a review. Drafts stay live; published reports are frozen.",
    href: '/reports',
    actions: [Capability.Report.CREATE],
  },
  requirements: {
    title: 'Requirements',
    description:
      'Requirements are atomic expectations for your application, measured through one or more metrics to determine if requirements are met.',
    href: '/requirements',
    actions: [Capability.Requirement.CREATE],
  },
  tasks: {
    title: 'Tasks',
    description:
      'Track and manage work items linked to tests, endpoints, and comments across your organization.',
    href: '/tasks',
    actions: [Capability.Task.CREATE],
  },
  testRuns: {
    title: 'Test Runs',
    description:
      'Executions of your test sets against AI endpoints. Track status, results, and history of each run.',
    href: '/test-runs',
    // New Test Run on the Runs tab, New schedule (EXECUTE) on the Schedules tab;
    // a loading view can't read the tab, so either counts.
    actions: [[Capability.TestRun.CREATE, Capability.TestRun.EXECUTE]],
  },
  testSets: {
    title: 'Test Sets',
    description:
      'Curated collections of tests you can version, share, and execute against your AI endpoints.',
    href: '/test-sets',
    actions: [
      Capability.File.IMPORT,
      [Capability.Garak.CREATE, Capability.Owasp.CREATE],
      Capability.TestSet.GENERATE,
      Capability.TestSet.CREATE,
    ],
  },
  tests: {
    title: 'Tests',
    description:
      'Individual test cases that evaluate your AI endpoints for quality, safety, and reliability.',
    href: '/tests',
    actions: [Capability.File.IMPORT, Capability.Test.CREATE],
  },
  tokens: {
    title: 'API Tokens',
    description:
      'Create API tokens to authenticate with the Rhesis SDK and programmatically manage your testing workflows from your code.',
    href: '/tokens',
    actions: [Capability.Token.CREATE],
  },
  tools: {
    title: 'Tools',
    description:
      'Connect tools and external services to import knowledge sources and enhance your evaluation workflows.',
    href: '/tools',
    actions: [Capability.Tool.CREATE],
  },
  traces: {
    title: 'Traces',
    description:
      'OpenTelemetry traces from test runs and live endpoint traffic. Inspect spans, metrics, and annotations.',
    href: '/traces',
    actions: [null],
  },
} as const satisfies Record<string, PageHeader>;

/** Models also describes embedding models when they are enabled. */
export const MODELS_DESCRIPTION_WITH_EMBEDDINGS =
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
  /** Export, add row and save: shown to everyone who can open the page. */
  actions: [null, null, null],
} as const;

export const NEW_METRIC_CRUMB = 'New Metric';
