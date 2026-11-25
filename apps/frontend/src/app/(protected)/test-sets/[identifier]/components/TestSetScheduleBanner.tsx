'use client';

import { Alert, Button } from '@mui/material';
import ScheduleIcon from '@mui/icons-material/Schedule';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { scheduleKeys } from '@/constants/query-keys';
import {
  SCHEDULE_STATUS,
  SCHEDULES_REFETCH_MS,
  TEST_RUNS_PARAM,
  TEST_RUNS_TAB,
} from '@/constants/test-run-schedules';
import {
  formatRunTime,
  timeUntil,
} from '@/components/common/run-drawer/schedule-form';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';

/** The schedule whose run comes first; schedules with nothing planned come last. */
function soonest(schedules: TestRunSchedule[]): TestRunSchedule | null {
  const planned = schedules
    .filter(s => s.status === SCHEDULE_STATUS.SCHEDULED && s.next_run_at)
    .sort((a, b) => (a.next_run_at ?? '').localeCompare(b.next_run_at ?? ''));
  return planned[0] ?? null;
}

/** Text of the banner. Exported for tests. */
export function bannerText(schedules: TestRunSchedule[]): string {
  const next = soonest(schedules);
  const nextText = next?.next_run_at
    ? `Next run ${formatRunTime(next.next_run_at, next.timezone)} (${timeUntil(next.next_run_at)})`
    : null;
  const allPaused = schedules.every(s => s.status === SCHEDULE_STATUS.PAUSED);
  if (schedules.length === 1) {
    const only = schedules[0];
    const lastRun =
      only.last_run?.pass_rate !== null &&
      only.last_run?.pass_rate !== undefined
        ? `Last run ${Math.round(only.last_run.pass_rate * 100)}% pass`
        : null;
    return [allPaused ? 'Paused' : 'Scheduled', only.repeats, nextText, lastRun]
      .filter(Boolean)
      .join(' · ');
  }
  return [
    `${schedules.length} schedules`,
    allPaused ? 'Paused' : null,
    nextText,
  ]
    .filter(Boolean)
    .join(' · ');
}

/** Under the test set header when the set has schedules. */
export default function TestSetScheduleBanner({
  testSetId,
}: {
  testSetId: string;
}) {
  const canRead = useCan(Capability.TestRun.READ);
  const { data } = useQuery({
    queryKey: scheduleKeys.forTestSet(testSetId),
    queryFn: () =>
      new ApiClientFactory()
        .getTestRunSchedulesClient()
        .list({ test_set_id: testSetId }),
    refetchInterval: SCHEDULES_REFETCH_MS,
    enabled: canRead,
  });
  // Finished schedules have nothing left to say here.
  const schedules = (data ?? []).filter(
    s => s.status !== SCHEDULE_STATUS.FINISHED
  );
  if (schedules.length === 0) return null;

  const overdue = schedules.some(s => s.overdue);
  const allPaused = schedules.every(s => s.status === SCHEDULE_STATUS.PAUSED);
  const href =
    schedules.length === 1
      ? `/test-runs/schedules/${schedules[0].id}`
      : `/test-runs?${TEST_RUNS_PARAM.TAB}=${TEST_RUNS_TAB.SCHEDULES}`;

  return (
    <Alert
      severity={overdue ? 'warning' : 'info'}
      variant={allPaused && !overdue ? 'outlined' : 'standard'}
      icon={<ScheduleIcon fontSize="inherit" />}
      sx={{ mb: 2 }}
      action={
        <Button component={Link} href={href} color="inherit" size="small">
          {schedules.length === 1 ? 'View schedule' : 'View'}
        </Button>
      }
    >
      {overdue ? 'Overdue · ' : ''}
      {bannerText(schedules)}
    </Alert>
  );
}
