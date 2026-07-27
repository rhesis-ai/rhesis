import { hitAll, hitAuthenticated, safetyThresholds, perEndpointThresholds, buildSummary } from './common.js';

// Spike test: sudden burst far above baseline, then recovery.
// Moderate profile: burst to 300 VUs for 1m, then drop back to a 5 VU
// baseline to observe recovery. ~3 minutes total.
export const options = {
  stages: [
    { duration: '30s', target: 5 },
    { duration: '30s', target: 300 },
    { duration: '1m', target: 300 },
    { duration: '30s', target: 5 },
    { duration: '1m', target: 5 },
  ],
  thresholds: { ...safetyThresholds(10000, 0.2), ...perEndpointThresholds() },
};

export default function () {
  hitAll();
  hitAuthenticated();
}

export function handleSummary(data) {
  return buildSummary(data, 'spike');
}
