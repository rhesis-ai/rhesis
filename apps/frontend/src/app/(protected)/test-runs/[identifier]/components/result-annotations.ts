import { ANNOTATION_TARGET_TYPES } from '@/utils/api-client/interfaces/annotation';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

/**
 * Reading the annotations a test result carries on its own payload.
 *
 * Only two questions are asked of this: has anyone annotated this result at
 * all, and which metric annotation is the latest. Both are answered from
 * `annotation_summary` without a request, which is what lets the results grid
 * and the tests table render an indicator per row synchronously. Anything
 * needing full rows (comments, `permitted_actions`, resolve state) fetches them
 * per entity through `useEntityAnnotations`.
 *
 * A metric annotation is either targeted at the metric or left on the result
 * with an `@metric` mention in its comment, so the mention parsing below is
 * part of answering "which metric does this judge".
 */

export interface ResultAnnotation {
  status?: { name?: string } | null;
  target_type?: string;
  reference?: string | null;
  comments?: string | null;
  user?: { name?: string } | null;
  updated_at?: string;
  resolved?: boolean;
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
function getResultAnnotations(result: TestResultDetail): ResultAnnotation[] {
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

function normalizeMetricName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

function metricNameMatches(
  a: string | null | undefined,
  b: string | null | undefined
): boolean {
  if (!a || !b) return false;
  return a === b || normalizeMetricName(a) === normalizeMetricName(b);
}

const METRIC_MARKUP_MENTION_REGEX = /@\[([^\]]+)\]\(metric:([^)]+)\)/gi;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** A mention names the metric by display text or by slug id, either counts. */
function commentMentionsMetric(comments: string, metricName: string): boolean {
  METRIC_MARKUP_MENTION_REGEX.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = METRIC_MARKUP_MENTION_REGEX.exec(comments)) !== null) {
    if (
      metricNameMatches(metricName, match[1]) ||
      metricNameMatches(metricName, match[2])
    ) {
      return true;
    }
  }

  const plainMention = new RegExp(
    `@${escapeRegExp(metricName)}(?=\\s|$|[.,!?;:])`,
    'i'
  );
  return plainMention.test(comments);
}

function commentMentionsAnyMetric(
  result: TestResultDetail,
  comments: string
): boolean {
  return Object.keys(result.test_metrics?.metrics ?? {}).some(metricName =>
    commentMentionsMetric(comments, metricName)
  );
}

function isTestResultAnnotationTarget(annotation: ResultAnnotation): boolean {
  const targetType = annotation.target_type;
  return !targetType || targetType === ANNOTATION_TARGET_TYPES.TEST_RESULT;
}

/** Test-level annotation, excluding metric @mentions left on the result target. */
function isExplicitTestLevelAnnotation(
  result: TestResultDetail,
  annotation: ResultAnnotation
): boolean {
  if (annotation.target_type === ANNOTATION_TARGET_TYPES.METRIC) return false;
  if (!isTestResultAnnotationTarget(annotation)) return false;
  return !commentMentionsAnyMetric(result, annotation.comments ?? '');
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
  const hasTestLevel = getResultAnnotations(result).some(annotation =>
    isExplicitTestLevelAnnotation(result, annotation)
  );
  return (
    hasTestLevel || getLatestMetricAnnotationForResult(result) !== undefined
  );
}
