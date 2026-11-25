'use client';

import DetailTabNav from '@/components/common/DetailTabNav';
import {
  SCHEDULE_STATUS,
  TEST_RUNS_TAB,
  type TestRunsTab,
} from '@/constants/test-run-schedules';
import { useSchedules } from './useSchedules';

const ORDER: TestRunsTab[] = [TEST_RUNS_TAB.RUNS, TEST_RUNS_TAB.SCHEDULES];

/** Runs | Schedules (n), where n counts the schedules still planned. */
export default function TestRunsTabs({
  value,
  onChange,
}: {
  value: TestRunsTab;
  onChange: (tab: TestRunsTab) => void;
}) {
  const schedules = useSchedules();
  const active = (schedules.data ?? []).filter(
    s => s.status === SCHEDULE_STATUS.SCHEDULED
  ).length;
  const tabs = ORDER.map((key, index) => ({
    key,
    label:
      key === TEST_RUNS_TAB.SCHEDULES && active > 0
        ? `Schedules (${active})`
        : key === TEST_RUNS_TAB.SCHEDULES
          ? 'Schedules'
          : 'Runs',
    id: `test-runs-tab-${index}`,
    'aria-controls': `test-runs-tabpanel-${index}`,
  }));
  return (
    <DetailTabNav
      tabs={tabs}
      activeIndex={ORDER.indexOf(value)}
      onChange={index => onChange(ORDER[index])}
      aria-label="Test runs sections"
      sx={{ mb: 3 }}
    />
  );
}
