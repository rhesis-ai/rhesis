import { ANNOTATION_TARGET_TYPES } from '@/utils/api-client/interfaces/annotation';
import {
  TestResultDetail,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import {
  getEffectiveTestResultStatus,
  isPassedStatusName,
} from '@/utils/test-result-status';
import { passRate } from '@/constants/outcomes';

/**
 * A metric's pre-review automated value. `override.original_value` is set
 * by the backend the moment a review changes the metric (see
 * _apply_metric_override); falls back to the live value when there's no
 * override.
 */
function metricAutomatedPass(metric: MetricResult): boolean {
  return metric.override?.original_value ?? metric.is_successful;
}

/**
 * The pre-review automated pass/fail for the whole result, from its metrics
 * alone. Every metric is read at its *automated* value (via
 * metricAutomatedPass), so a metric-level review that already flipped one
 * does not move this baseline -- otherwise a test-level review would be
 * compared against a number a human had already changed, and the
 * human-correction counts below would silently drift.
 *
 * The backend has no field for this yet, which is why it is still computed
 * here; see getEffectiveTestResultStatus for the trusted, backend-computed
 * *display* outcome, which is what everything other than correction
 * detection should use.
 */
function metricsOnlyAutomatedPass(result: TestResultDetail): boolean {
  const metrics = result.test_metrics?.metrics ?? {};
  const metricNames = Object.keys(metrics);
  if (metricNames.length === 0) return false;
  return metricNames.every(name => metricAutomatedPass(metrics[name]));
}

// The band scale lives in constants/outcomes.ts so every widget shares one.
// Re-exported here because this module is the established import site.
export type { ReviewBand, ReviewBandInfo } from '@/constants/outcomes';
export { getReviewBand } from '@/constants/outcomes';

export interface RequirementStat {
  name: string;
  total: number;
  passed: number;
  failed: number;
  passRate: number;
  /** True when a human annotation changed a test outcome in this requirement */
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
  /** Raw automated pass count before human annotations */
  automatedPassed?: number;
  automatedFailed?: number;
  /** Tests where effective outcome differs from automated metric result */
  humanReviewCount?: number;
  /** True when a human annotation changed this metric's outcome */
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

export function getEffectiveMetricSuccess(metric: {
  is_successful: boolean;
  override?: { original_value: boolean };
}): boolean {
  // is_successful already reflects a review that targeted this specific metric
  // (see _apply_metric_override on the backend). A whole-test review judges the
  // response as a whole, not this metric's own correctness, so it's deliberately
  // excluded here -- otherwise one corrected/failing metric would drag every
  // other metric on the same test into its own pass/fail count.
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

export interface ResultAnnotation {
  status?: { name?: string } | null;
  target_type?: string;
  reference?: string | null;
  comments?: string | null;
  user?: { name?: string } | null;
  updated_at?: string;
  resolved?: boolean;
}

function isTestResultAnnotationTarget(annotation: ResultAnnotation): boolean {
  const targetType = annotation.target_type;
  return !targetType || targetType === ANNOTATION_TARGET_TYPES.TEST_RESULT;
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

/** Test-level annotation, excluding metric @mentions left on the result target. */
export function isExplicitTestLevelAnnotation(
  result: TestResultDetail,
  annotation: ResultAnnotation
): boolean {
  if (annotation.target_type === ANNOTATION_TARGET_TYPES.METRIC) return false;
  if (!isTestResultAnnotationTarget(annotation)) return false;
  return !commentMentionsAnyMetric(result, annotation.comments ?? '');
}

function resultHasTestLevelAnnotation(result: TestResultDetail): boolean {
  return getResultAnnotations(result).some(annotation =>
    isExplicitTestLevelAnnotation(result, annotation)
  );
}

/** Latest metric-targeted annotation on a test result, if any. */
export function getLatestMetricAnnotationForResult(
  result: TestResultDetail
): ResultAnnotation | undefined {
  let latest: ResultAnnotation | undefined;
  let latestTime = -1;

  for (const annotation of getResultAnnotations(result)) {
    const onMetric = annotation.target_type === ANNOTATION_TARGET_TYPES.METRIC;
    if (
      !onMetric &&
      !commentMentionsAnyMetric(result, annotation.comments ?? '')
    ) {
      continue;
    }
    const time = annotation.updated_at
      ? new Date(annotation.updated_at).getTime()
      : 0;
    if (!latest || time >= latestTime) {
      latest = annotation;
      latestTime = time;
    }
  }

  return latest;
}

export function resultHasAnyHumanAnnotation(result: TestResultDetail): boolean {
  return (
    resultHasTestLevelAnnotation(result) ||
    getLatestMetricAnnotationForResult(result) !== undefined
  );
}

function isMetricAnnotationTarget(
  annotation: ResultAnnotation,
  metricName: string
): boolean {
  return (
    annotation.target_type === ANNOTATION_TARGET_TYPES.METRIC &&
    metricNameMatches(annotation.reference, metricName)
  );
}

/**
 * The annotations embedded on a result, one per target.
 *
 * `annotation_summary` is keyed `target_type` or `target_type:reference`, and
 * the backend has already reduced each target to its newest annotation, so
 * there is nothing to merge or de-duplicate here. Unlike the JSONB summary it
 * replaces, each entry carries its comment, so metric @mentions resolve off
 * the parent payload alone.
 */
export function getResultAnnotations(
  result: TestResultDetail
): ResultAnnotation[] {
  return Object.entries(result.annotation_summary ?? {}).map(
    ([key, entry]) => ({
      status: entry.status,
      target_type: entry.target_type,
      reference:
        entry.reference ??
        (key.includes(':') ? key.slice(key.indexOf(':') + 1) : null),
      comments: entry.comments,
      user: entry.user,
      updated_at: entry.updated_at,
    })
  );
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
): ResultAnnotation[] {
  return getResultAnnotations(result).filter(annotation =>
    commentMentionsMetric(annotation.comments ?? '', metricName)
  );
}

/** Annotations bearing on one metric: targeted at it, or @mentioning it. */
function iterMetricTargetAnnotations(
  result: TestResultDetail,
  metricName: string
): ResultAnnotation[] {
  const annotations: ResultAnnotation[] = [];
  const seen = new Set<ResultAnnotation>();

  const add = (annotation: ResultAnnotation | undefined) => {
    if (!annotation || seen.has(annotation)) return;
    seen.add(annotation);
    annotations.push(annotation);
  };

  for (const annotation of getResultAnnotations(result)) {
    if (isMetricAnnotationTarget(annotation, metricName)) add(annotation);
  }
  for (const annotation of collectMetricMentionsFromComments(
    result,
    metricName
  )) {
    add(annotation);
  }

  return annotations;
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

  const automatedPass = metricAutomatedPass(metric);

  for (const review of iterMetricTargetAnnotations(result, metricKey)) {
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
  return iterMetricTargetAnnotations(result, metricName).length > 0;
}

export function getResultRequirementName(
  result: TestResultDetail
): string | undefined {
  return (
    result.test?.requirement?.name ||
    (result.test as { requirement?: { name?: string } } | undefined)
      ?.requirement?.name
  );
}

/** True when a human test-level annotation changed the pass/fail outcome. */
export function testHasHumanCorrection(result: TestResultDetail): boolean {
  // No last_annotation fallback: the summary already holds the entity-level
  // annotation under its own key, so it is the same row.
  const automatedPass = metricsOnlyAutomatedPass(result);
  return getResultAnnotations(result)
    .filter(isTestResultAnnotationTarget)
    .some(
      annotation =>
        isPassedStatusName(annotation.status?.name ?? '') !== automatedPass
    );
}

export function countRequirementHumanCorrections(
  requirementName: string,
  testResults: TestResultDetail[]
): number {
  return testResults.filter(
    result =>
      getResultRequirementName(result) === requirementName &&
      testHasHumanCorrection(result)
  ).length;
}

export function buildRequirementCorrectionTooltip(
  requirementName: string,
  testResults: TestResultDetail[]
): string {
  const testCount = countRequirementHumanCorrections(
    requirementName,
    testResults
  );
  if (testCount === 0) return '';
  return `${testCount} test${testCount === 1 ? '' : 's'} corrected by human annotation`;
}

/** True when any test in this requirement had a test-level review correction. */
export function requirementHasHumanCorrection(
  requirementName: string,
  testResults: TestResultDetail[]
): boolean {
  return countRequirementHumanCorrections(requirementName, testResults) > 0;
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
  humanReviewCount = 0
): boolean {
  if (humanReviewCount > 0) {
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

export function computeAnnotationSummary(
  testResults: TestResultDetail[]
): ReviewSummary {
  let testReviewCount = 0;
  let testCorrectionCount = 0;

  for (const result of testResults) {
    if (!resultHasTestLevelAnnotation(result)) continue;

    testReviewCount++;

    const automatedPass = metricsOnlyAutomatedPass(result);
    const hasTestCorrection = getResultAnnotations(result)
      .filter(annotation => isExplicitTestLevelAnnotation(result, annotation))
      .some(
        annotation =>
          isPassedStatusName(annotation.status?.name ?? '') !== automatedPass
      );
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
      resultHasTestLevelAnnotation(result) ||
      getLatestMetricAnnotationForResult(result) !== undefined
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
    subtitle = 'No annotations yet';
  } else {
    const parts: string[] = [];
    if (testCorrectionCount > 0) {
      parts.push(`${testCorrectionCount} corrected (test)`);
    }
    if (metricCorrectionCount > 0) {
      parts.push(`${metricCorrectionCount} corrected (metric)`);
    }
    if (metricReviewedCount > 0) {
      parts.push(`${metricReviewedCount} annotated (metric)`);
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

export function aggregateRequirementStats(
  testResults: TestResultDetail[]
): RequirementStat[] {
  const map = new Map<string, { passed: number; total: number }>();

  for (const result of testResults) {
    const name = getResultRequirementName(result);
    if (!name) continue;
    const entry = map.get(name) ?? { passed: 0, total: 0 };
    entry.total += 1;
    if (getEffectiveTestResultStatus(result) === 'Pass') entry.passed += 1;
    map.set(name, entry);
  }

  return Array.from(map.entries()).map(([name, { passed, total }]) => {
    const humanCorrectionCount = countRequirementHumanCorrections(
      name,
      testResults
    );
    return {
      name,
      total,
      passed,
      failed: total - passed,
      passRate: passRate(passed, total - passed) ?? 0,
      hasHumanCorrection: humanCorrectionCount > 0,
      humanCorrectionCount,
      humanCorrectionTooltip: buildRequirementCorrectionTooltip(
        name,
        testResults
      ),
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
      const effective = getEffectiveMetricSuccess(m);
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
