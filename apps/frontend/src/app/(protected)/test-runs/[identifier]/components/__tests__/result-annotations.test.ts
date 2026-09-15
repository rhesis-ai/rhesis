import {
  getLatestMetricAnnotationForResult,
  resultHasAnyHumanAnnotation,
} from '../result-annotations';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { AnnotationSummaryEntry } from '@/utils/api-client/interfaces/annotation';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

let resultCounter = 0;
let annotationCounter = 0;

/** One entry as it arrives embedded on a result, entity-level unless told otherwise. */
function makeAnnotation(
  overrides: Partial<AnnotationSummaryEntry> = {}
): AnnotationSummaryEntry {
  annotationCounter += 1;
  return {
    annotation_id: u(100 + annotationCounter),
    target_type: 'test_result',
    reference: null,
    status: { name: 'Pass' },
    user: { name: 'Annotator' },
    comments: '',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

/** Key entries the way the backend does: target_type, or target_type:reference. */
function summaryOf(
  ...entries: AnnotationSummaryEntry[]
): Record<string, AnnotationSummaryEntry> {
  return Object.fromEntries(
    entries.map(entry => [
      entry.reference
        ? `${entry.target_type}:${entry.reference}`
        : entry.target_type,
      entry,
    ])
  );
}

function makeResult(
  overrides: Partial<TestResultDetail> & {
    metrics?: Record<
      string,
      { is_successful: boolean; override?: { original_value: boolean } }
    >;
  } = {}
): TestResultDetail {
  resultCounter += 1;
  const { metrics = {}, ...rest } = overrides;
  return {
    id: u(resultCounter),
    test_configuration_id: u(11),
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    test_metrics: { metrics, execution_time: 1 },
    status: { id: u(2), name: 'Pass' },
    annotation_summary: summaryOf(makeAnnotation()),
    ...rest,
  } as unknown as TestResultDetail;
}

describe('getLatestMetricAnnotationForResult', () => {
  it('finds an annotation targeted at the metric', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({
          target_type: 'metric',
          reference: 'Bias Detection',
          status: { name: 'Fail' },
        })
      ),
    });

    expect(getLatestMetricAnnotationForResult(result)?.status?.name).toBe(
      'Fail'
    );
  });

  it('matches a reference stored as a slug', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({
          target_type: 'metric',
          reference: 'bias-detection',
          status: { name: 'Fail' },
        })
      ),
    });

    expect(getLatestMetricAnnotationForResult(result)).toBeDefined();
  });

  it('finds an @[Metric](metric:slug) mention on a result-level annotation', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({
          comments: '@[Bias Detection](metric:bias-detection) should pass.',
          status: { name: 'Fail' },
        })
      ),
    });

    expect(getLatestMetricAnnotationForResult(result)?.status?.name).toBe(
      'Fail'
    );
  });

  it('finds a plain @Metric Name mention without markup', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({ comments: '@Bias Detection looks wrong to me.' })
      ),
    });

    expect(getLatestMetricAnnotationForResult(result)).toBeDefined();
  });

  it('ignores an annotation that names no metric', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({ comments: 'The whole answer is wrong.' })
      ),
    });

    expect(getLatestMetricAnnotationForResult(result)).toBeUndefined();
  });

  it('returns the newest when two metrics are annotated', () => {
    const result = makeResult({
      metrics: {
        'Bias Detection': { is_successful: true },
        Fluency: { is_successful: true },
      },
      annotation_summary: summaryOf(
        makeAnnotation({
          target_type: 'metric',
          reference: 'Bias Detection',
          status: { name: 'Fail' },
          updated_at: '2026-01-01T00:00:00Z',
        }),
        makeAnnotation({
          target_type: 'metric',
          reference: 'Fluency',
          status: { name: 'Pass' },
          updated_at: '2026-02-01T00:00:00Z',
        })
      ),
    });

    expect(getLatestMetricAnnotationForResult(result)?.reference).toBe(
      'Fluency'
    );
  });
});

describe('resultHasAnyHumanAnnotation', () => {
  it('is true for a plain test-level annotation', () => {
    expect(resultHasAnyHumanAnnotation(makeResult())).toBe(true);
  });

  it('is true when only a metric is annotated', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({ target_type: 'metric', reference: 'Bias Detection' })
      ),
    });

    expect(resultHasAnyHumanAnnotation(result)).toBe(true);
  });

  it('is false when nothing is annotated', () => {
    expect(
      resultHasAnyHumanAnnotation(makeResult({ annotation_summary: {} }))
    ).toBe(false);
  });

  // A result-level annotation whose comment names a metric is a metric
  // judgement, not a verdict on the whole result -- but it still counts as
  // somebody having annotated this result.
  it('is true for a result-level annotation that @mentions a metric', () => {
    const result = makeResult({
      metrics: { 'Bias Detection': { is_successful: true } },
      annotation_summary: summaryOf(
        makeAnnotation({
          comments: '@[Bias Detection](metric:bias-detection) is wrong.',
        })
      ),
    });

    expect(resultHasAnyHumanAnnotation(result)).toBe(true);
  });
});
