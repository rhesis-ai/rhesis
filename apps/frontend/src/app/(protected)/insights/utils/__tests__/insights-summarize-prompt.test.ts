import {
  MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS,
  buildInsightsSummarizePrompt,
  buildInsightsSummarizeSessionTitle,
  capArchitectInsightsTestRunIds,
  formatInsightsPeriodLabel,
} from '../insights-summarize-prompt';
import { DEFAULT_INSIGHTS_FILTERS, InsightsFilters } from '../../types';

function filters(
  overrides: Partial<InsightsFilters> = {}
): InsightsFilters {
  return { ...DEFAULT_INSIGHTS_FILTERS, ...overrides };
}

describe('capArchitectInsightsTestRunIds', () => {
  it('returns all ids when under the cap', () => {
    const ids = ['a', 'b', 'c'];
    expect(capArchitectInsightsTestRunIds(ids)).toEqual({
      ids,
      truncated: false,
      totalMatched: 3,
    });
  });

  it('takes the first 50 preserving order when over the cap', () => {
    const ids = Array.from({ length: 60 }, (_, i) => `run-${i}`);
    const result = capArchitectInsightsTestRunIds(ids);
    expect(result.truncated).toBe(true);
    expect(result.totalMatched).toBe(60);
    expect(result.ids).toHaveLength(MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS);
    expect(result.ids[0]).toBe('run-0');
    expect(result.ids[49]).toBe('run-49');
  });
});

describe('formatInsightsPeriodLabel', () => {
  it('uses time-range labels', () => {
    expect(
      formatInsightsPeriodLabel(filters({ timeRange: '7d' }))
    ).toBe('7D');
  });

  it('uses run count for explicit selection', () => {
    expect(
      formatInsightsPeriodLabel(
        filters({
          runFilterMode: 'testRuns',
          testRunIds: ['1', '2', '3'],
        })
      )
    ).toBe('3 runs');
  });
});

describe('buildInsightsSummarizeSessionTitle', () => {
  it('includes endpoint and period', () => {
    expect(
      buildInsightsSummarizeSessionTitle({
        endpointName: 'Chatbot',
        filters: filters({ timeRange: '1m' }),
      })
    ).toBe('Insights summary — Chatbot — 1M');
  });
});

describe('buildInsightsSummarizePrompt', () => {
  it('includes RUN_ANALYZE / Insights signals and visible behaviors', () => {
    const prompt = buildInsightsSummarizePrompt({
      endpointName: 'Chatbot',
      filters: filters({ timeRange: '7d' }),
      visibleBehaviorNames: ['Safety', 'Tone'],
      testRunIds: ['run-1', 'run-2'],
      truncated: false,
      totalMatched: 2,
    });

    expect(prompt).toContain('Summarize insights');
    expect(prompt).toContain('test results');
    expect(prompt).toContain('Insights handoff');
    expect(prompt).toContain('Endpoint: Chatbot');
    expect(prompt).toContain('Behaviors in scope: Safety, Tone');
    expect(prompt).toContain('run-1, run-2');
    expect(prompt).not.toContain('Note:');
  });

  it('discloses truncation for time-range (most recent)', () => {
    const prompt = buildInsightsSummarizePrompt({
      endpointName: 'API',
      filters: filters({ runFilterMode: 'timeRange', timeRange: '3m' }),
      visibleBehaviorNames: [],
      testRunIds: ['a'],
      truncated: true,
      totalMatched: 80,
    });
    expect(prompt).toContain('80 runs matched');
    expect(prompt).toContain('most recent');
  });

  it('discloses truncation for explicit selection (first 50 in order)', () => {
    const prompt = buildInsightsSummarizePrompt({
      endpointName: 'API',
      filters: filters({
        runFilterMode: 'testRuns',
        testRunIds: Array.from({ length: 60 }, (_, i) => `id-${i}`),
      }),
      visibleBehaviorNames: [],
      testRunIds: ['id-0'],
      truncated: true,
      totalMatched: 60,
    });
    expect(prompt).toContain('first 50 in selection order');
  });
});
