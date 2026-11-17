import type { ReportResultRule } from '@/utils/api-client/interfaces/report';

/** How a test that ran in several picked runs is counted. Mirrors the backend rules. */
export const RESULT_RULES: Record<
  ReportResultRule,
  { label: string; description: string }
> = {
  latest: {
    label: 'Latest run',
    description:
      "Each test counts once, with the latest run's result. Use it when later runs replace earlier ones.",
  },
  all: {
    label: 'All runs (average)',
    description:
      'Every result in every run counts, so pass rates are averages. Use it for repeated runs of the same tests.',
  },
  worst: {
    label: 'Worst result',
    description:
      'A test counts as failed if it failed in any run. The strictest choice for a release gate.',
  },
};
