import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

export function formatDuration(ms: number): string {
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

export function getRunExpectedTestCount(testRun: TestRunDetail): number | null {
  const fromRun = testRun.attributes?.total_tests;
  if (typeof fromRun === 'number' && fromRun > 0) return fromRun;

  const fromTestSet =
    testRun.test_configuration?.test_set?.attributes?.metadata?.total_tests;
  if (typeof fromTestSet === 'number' && fromTestSet > 0) return fromTestSet;

  return null;
}

export function resolveTurnCount(result: TestResultDetail): number {
  const fromOutput =
    result.test_output?.turns_used ??
    result.test_output?.stats?.total_turns ??
    result.test_output?.conversation_summary?.length;

  if (typeof fromOutput === 'number' && fromOutput > 0) return fromOutput;
  return 1;
}

export function formatAvgTurnSubtitle(avg: number | null): string {
  if (avg === null) return '';
  const rounded = Math.round(avg);
  const label = rounded === 1 ? 'turn' : 'turns';
  return `Avg. ${rounded} ${label}`;
}
