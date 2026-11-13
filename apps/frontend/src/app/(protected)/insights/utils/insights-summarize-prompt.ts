import {
  InsightsFilters,
  InsightsTimeRange,
  INSIGHTS_TIME_RANGE_OPTIONS,
} from '../types';

/** Hard cap for Architect handoff — agent tool cost scales with run count. */
export const MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS = 50;

export interface CapArchitectInsightsTestRunIdsResult {
  ids: string[];
  truncated: boolean;
  totalMatched: number;
}

/**
 * Cap run IDs for the Architect handoff.
 *
 * - Time-range mode: IDs are already recency-ordered (newest first) — take first 50.
 * - Explicit selection: preserve user-provided order — take first 50.
 */
export function capArchitectInsightsTestRunIds(
  testRunIds: string[]
): CapArchitectInsightsTestRunIdsResult {
  const totalMatched = testRunIds.length;
  if (totalMatched <= MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS) {
    return { ids: testRunIds, truncated: false, totalMatched };
  }
  return {
    ids: testRunIds.slice(0, MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS),
    truncated: true,
    totalMatched,
  };
}

export function formatInsightsPeriodLabel(
  filters: Pick<InsightsFilters, 'runFilterMode' | 'timeRange' | 'testRunIds'>
): string {
  if (filters.runFilterMode === 'testRuns') {
    const n = filters.testRunIds.length;
    return n > 0 ? `${n} runs` : 'all runs';
  }
  const option = INSIGHTS_TIME_RANGE_OPTIONS.find(
    o => o.value === filters.timeRange
  );
  return option?.label ?? filters.timeRange.toUpperCase();
}

export function buildInsightsSummarizeSessionTitle(input: {
  endpointName: string;
  filters: Pick<InsightsFilters, 'runFilterMode' | 'timeRange' | 'testRunIds'>;
}): string {
  const endpoint = input.endpointName.trim() || 'endpoint';
  const period = formatInsightsPeriodLabel(input.filters);
  return `Insights summary — ${endpoint} — ${period}`;
}

export interface BuildInsightsSummarizePromptInput {
  endpointName: string;
  filters: InsightsFilters;
  /** Requirement names currently visible (multi-select ∩ search). */
  visibleRequirementNames: string[];
  testRunIds: string[];
  truncated: boolean;
  totalMatched: number;
  timeRange?: InsightsTimeRange;
}

const SUMMARIZE_GROUPING = {
  requirement: {
    scopeLabel: 'Requirements in scope',
    dimension: 'requirement',
    noun: 'requirement',
  },
  impact: {
    scopeLabel: 'Requirement impacts in scope',
    dimension: 'impact',
    noun: 'impact',
  },
  parent: {
    scopeLabel: 'Parent requirements in scope',
    dimension: 'requirement_parent',
    noun: 'parent requirement',
  },
} as const;

export function buildInsightsSummarizePrompt(
  input: BuildInsightsSummarizePromptInput
): string {
  const period = formatInsightsPeriodLabel(input.filters);
  const requirements =
    input.visibleRequirementNames.length > 0
      ? input.visibleRequirementNames.join(', ')
      : 'all visible';
  const groupBy = input.filters.groupBy ?? 'requirement';
  const { scopeLabel, dimension, noun } = SUMMARIZE_GROUPING[groupBy];

  const truncationNote = input.truncated
    ? input.filters.runFilterMode === 'testRuns'
      ? `Note: ${input.totalMatched} runs matched; using the first ${MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS} in selection order.`
      : `Note: ${input.totalMatched} runs matched; using the ${MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS} most recent.`
    : null;

  const lines = [
    'Summarize insights for the Insights page view I was looking at.',
    '',
    'This is an Insights handoff — analyze these test results; do not show the menu',
    'and do not start exploration or create entities.',
    '',
    `Endpoint: ${input.endpointName.trim() || 'unknown'}`,
    `Period / runs: ${period}`,
    `${scopeLabel}: ${requirements}`,
    `Test run IDs (max ${MAX_ARCHITECT_INSIGHTS_TEST_RUN_IDS}): ${input.testRunIds.join(', ') || '(none)'}`,
  ];

  // The page's grouping and impact filter change the numbers, so the
  // re-fetch has to repeat them.
  if (groupBy !== 'requirement') {
    lines.push(`Group by: ${dimension} (get_insights group_by=[${dimension}])`);
  }
  const impactIds = input.filters.impactIds;
  if (impactIds !== null && impactIds.length > 0) {
    lines.push(`Impact filter (impact_ids): ${impactIds.join(', ')}`);
  }

  if (truncationNote) {
    lines.push(truncationNote);
  }

  lines.push(
    '',
    `Please re-fetch stats for this scope, summarize overall and by ${noun}/metric,`,
    'then sample a few failed results and call out patterns and next steps.'
  );

  return lines.join('\n');
}
