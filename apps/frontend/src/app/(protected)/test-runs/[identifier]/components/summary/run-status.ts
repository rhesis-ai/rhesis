import type { RunStatus } from '@/constants/test-runs';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';

export interface DerivedRunStatus {
  status: RunStatus;
  total: number;
  passed: number;
  failed: number;
  executionErrors: number;
  passRate: number | null;
  duration: number | null;
  avgTurnDepth: number | null;
}

function resolveTurnCount(result: TestResultDetail): number {
  const fromOutput =
    result.test_output?.turns_used ??
    result.test_output?.stats?.total_turns ??
    result.test_output?.conversation_summary?.length;

  if (typeof fromOutput === 'number' && fromOutput > 0) {
    return fromOutput;
  }

  return 1;
}

export function deriveRunStatus(
  testRun: TestRunDetail,
  testResults?: TestResultDetail[]
): DerivedRunStatus {
  const results = testResults ?? [];
  const total = results.length;
  let passed = 0;
  let failed = 0;
  let executionErrors = 0;
  let totalTurns = 0;

  for (const result of results) {
    const s = getEffectiveTestResultStatus(result);
    if (s === 'Pass') passed++;
    else if (s === 'Fail') failed++;
    else executionErrors++;
    totalTurns += resolveTurnCount(result);
  }

  const passRate = total > 0 ? passed / total : null;
  const avgTurnDepth = total > 0 ? totalTurns / total : null;

  const startedAt = testRun.attributes?.started_at;
  const completedAt = testRun.attributes?.completed_at;
  let duration: number | null = null;
  if (typeof startedAt === 'string' && typeof completedAt === 'string') {
    duration = Math.abs(
      new Date(completedAt).getTime() - new Date(startedAt).getTime()
    );
  }

  const backendStatus = testRun.status?.name?.toLowerCase();
  let status: RunStatus;

  if (backendStatus === 'cancelled') status = 'cancelled';
  else if (backendStatus === 'queued') status = 'queued';
  else if (backendStatus === 'progress') status = 'progress';
  else if (backendStatus === 'partial') status = 'partial';
  else if (backendStatus === 'failed') status = 'failed';
  else if (backendStatus === 'completed') status = 'completed';
  else if (!completedAt && startedAt) status = 'progress';
  else if (completedAt && executionErrors > 0 && executionErrors < total)
    status = 'partial';
  else if (executionErrors === total && total > 0) status = 'failed';
  else status = 'completed';

  return {
    status,
    total,
    passed,
    failed,
    executionErrors,
    passRate,
    duration,
    avgTurnDepth,
  };
}
