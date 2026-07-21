import { hitAll, hitAuthenticated, safetyThresholds, perEndpointThresholds, buildSummary } from './common.js';

// Soak test: sustained moderate load for an extended period, watching for
// memory leaks / latency drift / connection exhaustion over time.
// Moderate profile: 20 VUs held for 1 hour. ~64 minutes total.
export const options = {
  stages: [
    { duration: '2m', target: 20 },
    { duration: '60m', target: 20 },
    { duration: '2m', target: 0 },
  ],
  thresholds: { ...safetyThresholds(6000, 0.1), ...perEndpointThresholds() },
};

export default function () {
  hitAll();
  hitAuthenticated();
}

export function handleSummary(data) {
  return buildSummary(data, 'soak');
}
