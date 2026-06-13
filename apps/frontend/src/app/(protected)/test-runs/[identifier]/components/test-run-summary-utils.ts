import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';

export type ReviewBand = 'ok' | 'watch' | 'review';

export interface ReviewBandInfo {
  band: ReviewBand;
  label: string;
  colorKey: 'success' | 'warning' | 'error';
}

export function getReviewBand(passRate: number): ReviewBandInfo {
  if (passRate >= 100) {
    return { band: 'ok', label: 'OK', colorKey: 'success' };
  }
  if (passRate >= 70) {
    return { band: 'watch', label: 'Watch', colorKey: 'warning' };
  }
  return { band: 'review', label: 'Needs Review', colorKey: 'error' };
}

export interface BehaviorStat {
  name: string;
  total: number;
  passed: number;
  failed: number;
  passRate: number;
}

export interface MetricStat {
  name: string;
  total: number;
  passed: number;
  failed: number;
  failRate: number;
}

export function aggregateBehaviorStats(
  testResults: TestResultDetail[]
): BehaviorStat[] {
  const map = new Map<string, { passed: number; total: number }>();

  for (const result of testResults) {
    const name =
      result.test?.behavior?.name ||
      (result.test as { behavior?: { name?: string } } | undefined)?.behavior
        ?.name;
    if (!name) continue;
    const entry = map.get(name) ?? { passed: 0, total: 0 };
    entry.total += 1;
    if (getEffectiveTestResultStatus(result) === 'Pass') entry.passed += 1;
    map.set(name, entry);
  }

  return Array.from(map.entries()).map(([name, { passed, total }]) => ({
    name,
    total,
    passed,
    failed: total - passed,
    passRate: total > 0 ? (passed / total) * 100 : 0,
  }));
}

export function aggregateMetricStats(
  testResults: TestResultDetail[]
): MetricStat[] {
  const map = new Map<string, { passed: number; total: number }>();

  for (const result of testResults) {
    const metrics = result.test_metrics?.metrics ?? {};
    for (const [name, m] of Object.entries(metrics)) {
      const entry = map.get(name) ?? { passed: 0, total: 0 };
      entry.total += 1;
      if (m.is_successful) entry.passed += 1;
      map.set(name, entry);
    }
  }

  return Array.from(map.entries()).map(([name, { passed, total }]) => ({
    name,
    total,
    passed,
    failed: total - passed,
    failRate: total > 0 ? ((total - passed) / total) * 100 : 0,
  }));
}
