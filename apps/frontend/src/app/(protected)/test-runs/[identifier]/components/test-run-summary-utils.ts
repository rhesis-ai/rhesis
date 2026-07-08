import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import {
  getEffectiveTestResultStatus,
  getTestResultStatus,
  isPassedStatusName,
} from '@/utils/test-result-status';

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
  /** Raw automated pass count before human reviews */
  automatedPassed?: number;
  automatedFailed?: number;
  /** Tests where effective outcome differs from automated metric result */
  humanReviewCount?: number;
}

export interface ReviewSummary {
  testReviewCount: number;
  metricReviewCount: number;
  correctionCount: number;
  headline: string;
  subtitle: string;
}

/** True when reviewed passed/failed counts differ from automated counts. */
export function metricWasCorrected(stat: MetricStat): boolean {
  if (stat.automatedPassed === undefined) return false;
  const automatedFailed =
    stat.automatedFailed ?? stat.total - stat.automatedPassed;
  return (
    stat.passed !== stat.automatedPassed || stat.failed !== automatedFailed
  );
}

export function computeReviewSummary(
  testResults: TestResultDetail[]
): ReviewSummary {
  let testReviewCount = 0;
  let testCorrectionCount = 0;

  for (const result of testResults) {
    if (!result.last_review) continue;
    testReviewCount++;
    const reviewedPass = isPassedStatusName(
      result.last_review.status?.name ?? ''
    );
    const automatedPass = getTestResultStatus(result) === 'Pass';
    if (reviewedPass !== automatedPass) {
      testCorrectionCount++;
    }
  }

  let metricReviewCount = 0;
  let metricCorrectionCount = 0;

  for (const result of testResults) {
    for (const metric of Object.values(result.test_metrics?.metrics ?? {})) {
      if (!metric.override) continue;
      metricReviewCount++;
      if (metric.override.original_value !== metric.is_successful) {
        metricCorrectionCount++;
      }
    }
  }

  const correctionCount = testCorrectionCount + metricCorrectionCount;
  const totalReviews = testReviewCount + metricReviewCount;

  let headline: string;
  if (correctionCount > 0) {
    headline = `${correctionCount} corrected`;
  } else if (totalReviews > 0) {
    headline = `${totalReviews} reviewed`;
  } else {
    headline = '0';
  }

  let subtitle: string;
  if (totalReviews === 0) {
    subtitle = 'No reviews yet';
  } else {
    const parts: string[] = [];
    if (testReviewCount > 0) {
      parts.push(`${testReviewCount} test${testReviewCount === 1 ? '' : 's'}`);
    }
    if (metricReviewCount > 0) {
      parts.push(
        `${metricReviewCount} metric${metricReviewCount === 1 ? '' : 's'}`
      );
    }
    subtitle = parts.join(' · ');
    if (correctionCount === 0) {
      subtitle += ' · confirmed';
    }
  }

  return {
    testReviewCount,
    metricReviewCount,
    correctionCount,
    headline,
    subtitle,
  };
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
  const map = new Map<
    string,
    {
      passed: number;
      total: number;
      automatedPassed: number;
      humanReviewCount: number;
    }
  >();

  for (const result of testResults) {
    const metrics = result.test_metrics?.metrics ?? {};
    for (const [name, m] of Object.entries(metrics)) {
      const entry = map.get(name) ?? {
        passed: 0,
        total: 0,
        automatedPassed: 0,
        humanReviewCount: 0,
      };
      entry.total += 1;
      const automated =
        m.override?.original_value !== undefined
          ? m.override.original_value
          : m.is_successful;
      const effective = getEffectiveMetricSuccess(result, m);
      if (automated) entry.automatedPassed += 1;
      if (effective) entry.passed += 1;
      if (m.override || automated !== effective) entry.humanReviewCount += 1;
      map.set(name, entry);
    }
  }

  return Array.from(map.entries()).map(
    ([name, { passed, total, automatedPassed, humanReviewCount }]) => ({
      name,
      total,
      passed,
      failed: total - passed,
      failRate: total > 0 ? ((total - passed) / total) * 100 : 0,
      automatedPassed,
      automatedFailed: total - automatedPassed,
      humanReviewCount,
    })
  );
}

export function getEffectiveMetricSuccess(
  test: TestResultDetail,
  metric: { is_successful: boolean; override?: { original_value: boolean } }
): boolean {
  if (metric.override) {
    return metric.is_successful;
  }

  const overall = getEffectiveTestResultStatus(test);
  if (overall === 'Pass' && !metric.is_successful) {
    return true;
  }
  if (overall === 'Fail' && metric.is_successful) {
    return false;
  }

  return metric.is_successful;
}
