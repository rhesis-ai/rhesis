// Kept apart from NewMetricForm so the route's loading view can draw the same
// header and stepper without pulling the form in.

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
    default:
      return 'Create New Metric';
  }
}
