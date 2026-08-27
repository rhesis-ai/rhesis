import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

export interface DerivedRunStatus {
  duration: number | null;
}

/**
 * Wall-clock duration from the run's own timestamps. Pass/fail/error
 * tallying used to live here too, computed by looping test results
 * client-side -- deleted, since the verdict-matrix endpoint's `kpis`
 * already carries the backend-computed counts (see
 * services/test_run.py:get_verdict_matrix), and this function's only
 * production caller (KpiRow.tsx) never even passed test results in
 * to populate them.
 */
export function deriveRunStatus(testRun: TestRunDetail): DerivedRunStatus {
  const startedAt = testRun.attributes?.started_at;
  const completedAt = testRun.attributes?.completed_at;
  let duration: number | null = null;
  if (typeof startedAt === 'string' && typeof completedAt === 'string') {
    duration = Math.abs(
      new Date(completedAt).getTime() - new Date(startedAt).getTime()
    );
  }

  return { duration };
}
