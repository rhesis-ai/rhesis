import { hitAll, hitAuthenticated, safetyThresholds, perEndpointThresholds, buildSummary } from './common.js';

// Load test: steady realistic traffic, ramped up and held.
// Moderate profile: ramp to 50 VUs, hold, ramp down. ~18 minutes total.
export const options = {
  stages: [
    { duration: '5m', target: 50 },
    { duration: '10m', target: 50 },
    { duration: '3m', target: 0 },
  ],
  thresholds: { ...safetyThresholds(5000, 0.1), ...perEndpointThresholds() },
};

export default function () {
  hitAll();
  hitAuthenticated();
}

export function handleSummary(data) {
  return buildSummary(data, 'load');
}
