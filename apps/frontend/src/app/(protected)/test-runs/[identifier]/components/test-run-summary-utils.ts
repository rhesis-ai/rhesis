import {
  REVIEW_TARGET_TYPES,
  TestResultDetail,
  type MetricPassRates,
  type PassFailStats,
} from '@/utils/api-client/interfaces/test-results';
import {
  getAutomatedMetricPass,
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
  /** True when a human review changed a test outcome in this behavior */
  hasHumanCorrection?: boolean;
  humanCorrectionCount?: number;
  humanCorrectionTooltip?: string;
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
  /** True when a human review changed this metric's outcome */
  hasHumanCorrection?: boolean;
  /** True when any human @metric review exists for this metric */
  hasMetricReview?: boolean;
}

export interface ReviewSummary {
  testReviewCount: number;
  metricReviewCount: number;
  testCorrectionCount: number;
  metricCorrectionCount: number;
  correctionCount: number;
  headline: string;
  subtitle: string;
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

function normalizeMetricName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

export function metricNameMatches(
  a: string | null | undefined,
  b: string | null | undefined
): boolean {
  if (!a || !b) return false;
  return a === b || normalizeMetricName(a) === normalizeMetricName(b);
}

export function findMetricKey(
  result: TestResultDetail,
  metricName: string
): string | undefined {
  const metrics = result.test_metrics?.metrics ?? {};
  if (metricName in metrics) return metricName;
  return Object.keys(metrics).find(key => metricNameMatches(key, metricName));
}

export interface ResultReview {
  status?: { name?: string };
  target?: { type?: string; reference?: string | null };
  comments?: string;
  user?: { name?: string };
  updated_at?: string;
}

function isTestResultReviewTarget(review: ResultReview): boolean {
  const targetType = review.target?.type;
  return (
    !targetType ||
    targetType === REVIEW_TARGET_TYPES.TEST_RESULT ||
    targetType === 'test'
  );
}

function commentMentionsAnyMetric(
  result: TestResultDetail,
  comments: string
): boolean {
  const metrics = Object.keys(result.test_metrics?.metrics ?? {});
  return metrics.some(metricName =>
    commentMentionsMetric(comments, metricName)
  );
}

/** Test-level review, excluding metric @mentions stored under test_result target. */
export function isExplicitTestLevelReview(
  result: TestResultDetail,
  review: ResultReview
): boolean {
  if (review.target?.type === REVIEW_TARGET_TYPES.METRIC) return false;
  if (!isTestResultReviewTarget(review)) return false;
  return !commentMentionsAnyMetric(result, review.comments ?? '');
}

function resultHasTestLevelReview(result: TestResultDetail): boolean {
  if (
    getResultReviews(result).some(review =>
      isExplicitTestLevelReview(result, review)
    )
  ) {
    return true;
  }

  return (
    !!result.last_review &&
    isExplicitTestLevelReview(result, result.last_review)
  );
}

/** Latest metric-targeted review on a test result, if any. */
export function getLatestMetricReviewForResult(
  result: TestResultDetail
): ResultReview | undefined {
  let latest: (ResultReview & { updated_at?: string }) | undefined;
  let latestTime = -1;

  const consider = (review: ResultReview & { updated_at?: string }) => {
    const time = review.updated_at ? new Date(review.updated_at).getTime() : 0;
    if (!latest || time >= latestTime) {
      latest = review;
      latestTime = time;
    }
  };

  for (const review of result.test_reviews?.reviews ?? []) {
    const isMetricTarget = review.target?.type === REVIEW_TARGET_TYPES.METRIC;
    const mentionsMetric = commentMentionsAnyMetric(
      result,
      review.comments ?? ''
    );
    if (isMetricTarget || mentionsMetric) {
      consider(review);
    }
  }

  if (latest) return latest;

  for (const metricKey of Object.keys(result.test_metrics?.metrics ?? {})) {
    for (const review of iterMetricTargetReviews(result, metricKey)) {
      consider(review as ResultReview & { updated_at?: string });
    }
  }

  return latest;
}

export function resultHasAnyHumanReview(result: TestResultDetail): boolean {
  return (
    resultHasTestLevelReview(result) ||
    getLatestMetricReviewForResult(result) !== undefined
  );
}

function isMetricReviewTarget(
  review: ResultReview,
  metricName: string
): boolean {
  return (
    review.target?.type === REVIEW_TARGET_TYPES.METRIC &&
    metricNameMatches(review.target.reference, metricName)
  );
}

/** Collect reviews from test_reviews JSON, merged with review_summary. */
export function getResultReviews(result: TestResultDetail): ResultReview[] {
  const merged: ResultReview[] = [];
  const seenIds = new Set<string>();

  const addReview = (review: ResultReview, reviewId?: string) => {
    const key =
      reviewId ??
      `${review.target?.type ?? 'unknown'}:${review.target?.reference ?? ''}:${review.status?.name ?? ''}`;
    if (seenIds.has(key)) return;
    seenIds.add(key);
    merged.push(review);
  };

  for (const review of result.test_reviews?.reviews ?? []) {
    const reviewId = (review as { review_id?: string }).review_id;
    addReview(review, reviewId);
  }

  for (const [key, entry] of Object.entries(result.review_summary ?? {})) {
    addReview(
      {
        status: entry.status,
        target: {
          type: entry.target_type,
          reference:
            entry.reference ??
            (key.includes(':') ? key.slice(key.indexOf(':') + 1) : null),
        },
        comments: '',
      },
      entry.review_id ?? key
    );
  }

  return merged;
}

const METRIC_MARKUP_MENTION_REGEX = /@\[([^\]]+)\]\(metric:([^)]+)\)/gi;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function commentMentionsMetric(comments: string, metricName: string): boolean {
  METRIC_MARKUP_MENTION_REGEX.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = METRIC_MARKUP_MENTION_REGEX.exec(comments)) !== null) {
    if (metricMentionMatchesReview(metricName, match[1], match[2])) {
      return true;
    }
  }

  const plainMention = new RegExp(
    `@${escapeRegExp(metricName)}(?=\\s|$|[.,!?;:])`,
    'i'
  );
  return plainMention.test(comments);
}

function metricMentionMatchesReview(
  metricName: string,
  mentionDisplay: string,
  mentionId: string
): boolean {
  return (
    metricNameMatches(metricName, mentionDisplay) ||
    metricNameMatches(metricName, mentionId)
  );
}

function collectMetricMentionsFromComments(
  result: TestResultDetail,
  metricName: string
): ResultReview[] {
  const reviews: ResultReview[] = [];

  for (const review of getResultReviews(result)) {
    if (commentMentionsMetric(review.comments ?? '', metricName)) {
      reviews.push(review);
    }
  }

  return reviews;
}

function iterMetricTargetReviews(
  result: TestResultDetail,
  metricName: string
): ResultReview[] {
  const reviews: ResultReview[] = [];
  const seen = new Set<ResultReview>();

  const addReview = (review: ResultReview | undefined) => {
    if (!review || seen.has(review)) return;
    seen.add(review);
    reviews.push(review);
  };

  for (const review of getResultReviews(result)) {
    if (isMetricReviewTarget(review, metricName)) {
      addReview(review);
    }
  }

  for (const [key, entry] of Object.entries(result.review_summary ?? {})) {
    const summaryMetricRef = key.startsWith('metric:')
      ? key.slice('metric:'.length)
      : null;
    const matchesSummary =
      (entry.target_type === REVIEW_TARGET_TYPES.METRIC &&
        metricNameMatches(entry.reference, metricName)) ||
      (summaryMetricRef !== null &&
        metricNameMatches(summaryMetricRef, metricName));

    if (matchesSummary) {
      addReview({
        status: entry.status,
        target: {
          type: entry.target_type,
          reference: entry.reference ?? summaryMetricRef,
        },
      });
    }
  }

  for (const review of collectMetricMentionsFromComments(result, metricName)) {
    addReview(review);
  }

  return reviews;
}

/** True when a metric-level @mention review changed this metric's outcome. */
export function isMetricCorrected(
  result: TestResultDetail,
  metricKey: string
): boolean {
  const metric = result.test_metrics?.metrics?.[metricKey];
  if (!metric) return false;

  if (
    metric.override &&
    metric.override.original_value !== metric.is_successful
  ) {
    return true;
  }

  const automatedPass = getAutomatedMetricPass(metric);

  for (const review of iterMetricTargetReviews(result, metricKey)) {
    const reviewedPass = isPassedStatusName(review.status?.name ?? '');
    if (reviewedPass !== automatedPass) {
      return true;
    }
  }

  return false;
}

/** True when any @metric review targets this metric on a test result. */
export function hasMetricTargetedReview(
  result: TestResultDetail,
  metricName: string
): boolean {
  return iterMetricTargetReviews(result, metricName).length > 0;
}

export function findMetricPassRateKey(
  metricPassRates: MetricPassRates | undefined,
  name: string
): string | undefined {
  if (!metricPassRates) return undefined;
  if (name in metricPassRates) return name;
  return Object.keys(metricPassRates).find(key => metricNameMatches(key, name));
}

export function getMetricPassRateFromStats(
  metricPassRates: MetricPassRates | undefined,
  name: string
): PassFailStats | undefined {
  const key = findMetricPassRateKey(metricPassRates, name);
  return key ? metricPassRates?.[key] : undefined;
}

/** True when backend stats report a metric-level human review override. */
export function metricHasReviewCorrectionFromStats(
  metricPassRates: MetricPassRates | undefined,
  name: string
): boolean {
  const entry = getMetricPassRateFromStats(metricPassRates, name);
  return (entry?.human_review_count ?? 0) > 0;
}

export function getResultBehaviorName(
  result: TestResultDetail
): string | undefined {
  return (
    result.test?.behavior?.name ||
    (result.test as { behavior?: { name?: string } } | undefined)?.behavior
      ?.name
  );
}

/** True when a human test-level review changed the pass/fail outcome. */
export function testHasHumanCorrection(result: TestResultDetail): boolean {
  const testReviews = getResultReviews(result).filter(isTestResultReviewTarget);
  const reviewsToCheck =
    testReviews.length > 0
      ? testReviews
      : result.last_review
        ? [result.last_review]
        : [];

  const automatedPass = getTestResultStatus(result) === 'Pass';

  return reviewsToCheck.some(review => {
    const reviewedPass = isPassedStatusName(review.status?.name ?? '');
    return reviewedPass !== automatedPass;
  });
}

export function countBehaviorHumanCorrections(
  behaviorName: string,
  testResults: TestResultDetail[]
): number {
  return testResults.filter(
    result =>
      getResultBehaviorName(result) === behaviorName &&
      testHasHumanCorrection(result)
  ).length;
}

export function buildBehaviorCorrectionTooltip(
  behaviorName: string,
  testResults: TestResultDetail[]
): string {
  const testCount = countBehaviorHumanCorrections(behaviorName, testResults);
  if (testCount === 0) return '';
  return `${testCount} test${testCount === 1 ? '' : 's'} corrected by human review`;
}

/** True when any test in this behavior had a test-level review correction. */
export function behaviorHasHumanCorrection(
  behaviorName: string,
  testResults: TestResultDetail[]
): boolean {
  return countBehaviorHumanCorrections(behaviorName, testResults) > 0;
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

/** True when any @metric review targets this metric across the run. */
export function metricHasHumanReview(
  metricName: string,
  testResults: TestResultDetail[]
): boolean {
  return testResults.some(result =>
    hasMetricTargetedReview(result, metricName)
  );
}

/** True when backend stats or test payloads show a metric-level correction. */
export function metricShowsHumanCorrection(
  metricName: string,
  testResults: TestResultDetail[],
  metricPassRates?: MetricPassRates
): boolean {
  if (metricHasReviewCorrectionFromStats(metricPassRates, metricName)) {
    return true;
  }
  return metricHasHumanCorrection(metricName, testResults);
}

/** True only when a human metric-level review (@metric) changed this metric. */
export function metricHasHumanCorrection(
  metricName: string,
  testResults: TestResultDetail[]
): boolean {
  return testResults.some(result => {
    const metricKey = findMetricKey(result, metricName);
    return metricKey ? isMetricCorrected(result, metricKey) : false;
  });
}

export function computeReviewSummary(
  testResults: TestResultDetail[]
): ReviewSummary {
  let testReviewCount = 0;
  let testCorrectionCount = 0;

  for (const result of testResults) {
    if (!resultHasTestLevelReview(result)) continue;

    testReviewCount++;

    const testReviews = getResultReviews(result).filter(review =>
      isExplicitTestLevelReview(result, review)
    );
    const reviewsToCheck =
      testReviews.length > 0
        ? testReviews
        : result.last_review &&
            isExplicitTestLevelReview(result, result.last_review)
          ? [result.last_review]
          : [];
    const automatedPass = getTestResultStatus(result) === 'Pass';

    const hasTestCorrection = reviewsToCheck.some(review => {
      const reviewedPass = isPassedStatusName(review.status?.name ?? '');
      return reviewedPass !== automatedPass;
    });
    if (hasTestCorrection) {
      testCorrectionCount++;
    }
  }

  let metricReviewCount = 0;
  let metricCorrectionCount = 0;

  for (const result of testResults) {
    const reviewedMetrics = new Set<string>();

    for (const metricKey of Object.keys(result.test_metrics?.metrics ?? {})) {
      const metric = result.test_metrics?.metrics?.[metricKey];
      const hasOverride =
        !!metric?.override &&
        metric.override.original_value !== metric.is_successful;
      if (hasMetricTargetedReview(result, metricKey) || hasOverride) {
        reviewedMetrics.add(metricKey);
      }
    }

    for (const metricKey of reviewedMetrics) {
      metricReviewCount++;
      if (isMetricCorrected(result, metricKey)) {
        metricCorrectionCount++;
      }
    }
  }

  const correctionCount = testCorrectionCount + metricCorrectionCount;
  const totalReviews = testReviewCount + metricReviewCount;
  const metricReviewedCount = Math.max(
    0,
    metricReviewCount - metricCorrectionCount
  );
  const reviewedTestCount = testResults.filter(
    result =>
      resultHasTestLevelReview(result) ||
      getLatestMetricReviewForResult(result) !== undefined
  ).length;

  let headline: string;
  if (reviewedTestCount > 0) {
    headline = `${reviewedTestCount} test${reviewedTestCount === 1 ? '' : 's'}`;
  } else if (totalReviews === 0) {
    headline = '0';
  } else {
    headline = `${metricReviewCount} metric${metricReviewCount === 1 ? '' : 's'}`;
  }

  let subtitle: string;
  if (totalReviews === 0) {
    subtitle = 'No reviews yet';
  } else {
    const parts: string[] = [];
    if (testCorrectionCount > 0) {
      parts.push(`${testCorrectionCount} corrected (test)`);
    }
    if (metricCorrectionCount > 0) {
      parts.push(`${metricCorrectionCount} corrected (metric)`);
    }
    if (metricReviewedCount > 0) {
      parts.push(`${metricReviewedCount} reviewed (metric)`);
    }
    if (parts.length === 0) {
      subtitle = 'confirmed';
    } else if (
      metricReviewCount > 0 &&
      testReviewCount > 0 &&
      parts.length === 1
    ) {
      subtitle = `${parts.join(' · ')} · ${metricReviewCount} metric${metricReviewCount === 1 ? '' : 's'}`;
    } else {
      subtitle = parts.join(' · ');
    }
  }

  return {
    testReviewCount,
    metricReviewCount,
    testCorrectionCount,
    metricCorrectionCount,
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
    const name = getResultBehaviorName(result);
    if (!name) continue;
    const entry = map.get(name) ?? { passed: 0, total: 0 };
    entry.total += 1;
    if (getEffectiveTestResultStatus(result) === 'Pass') entry.passed += 1;
    map.set(name, entry);
  }

  return Array.from(map.entries()).map(([name, { passed, total }]) => {
    const humanCorrectionCount = countBehaviorHumanCorrections(
      name,
      testResults
    );
    return {
      name,
      total,
      passed,
      failed: total - passed,
      passRate: total > 0 ? (passed / total) * 100 : 0,
      hasHumanCorrection: humanCorrectionCount > 0,
      humanCorrectionCount,
      humanCorrectionTooltip: buildBehaviorCorrectionTooltip(name, testResults),
    };
  });
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
      const hasMetricOverride =
        m.override && m.override.original_value !== m.is_successful;
      if (hasMetricOverride) {
        entry.humanReviewCount += 1;
      }
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
      hasHumanCorrection: metricHasHumanCorrection(name, testResults),
    })
  );
}
