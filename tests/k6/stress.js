import { hitAll, hitAuthenticated, safetyThresholds, perEndpointThresholds, buildSummary } from './common.js';

// Stress test: push well past normal load to find the breaking point.
// Moderate profile: staged ramp to 200 VUs. Auto-aborts via safetyThresholds
// if error rate or p95 latency degrades badly, so it won't blindly hammer
// prod once it's already failing. ~20 minutes total if it runs to completion.
export const options = {
  stages: [
    { duration: '3m', target: 50 },
    { duration: '3m', target: 100 },
    { duration: '3m', target: 150 },
    { duration: '3m', target: 200 },
    { duration: '5m', target: 200 },
    { duration: '3m', target: 0 },
  ],
  thresholds: { ...safetyThresholds(8000, 0.15), ...perEndpointThresholds() },
};

export default function () {
  hitAll();
  hitAuthenticated();
}

export function handleSummary(data) {
  return buildSummary(data, 'stress');
}
