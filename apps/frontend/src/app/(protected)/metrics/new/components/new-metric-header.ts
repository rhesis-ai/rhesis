// Kept apart from NewMetricForm so the route's loading view can draw the same
// header and stepper without pulling the form in.

import { METRIC_TYPES } from '@/constants/metric-types';

export const NEW_METRIC_STEPS = [
  'Metric Information and Criteria',
  'Confirmation',
];

/** The page title for a `?type=` value. */
export function newMetricTitle(type: string | null): string {
  switch (type) {
    case 'grading':
      return 'Create Grading Criteria Metric';
    case 'api-call':
      return 'Create API Call Metric';
    case 'custom-code':
      return 'Create Custom Code Metric';
    case 'custom-prompt':
      return 'Create Custom Prompt Metric';
    case 'framework':
      return 'Create Framework Metric';
    case METRIC_TYPES.RULE:
      return 'Create Rule';
    default:
      return 'Create New Metric';
  }
}
