'use client';

import DetailTabNav from '@/components/common/DetailTabNav';
import {
  TEST_RUNS_TAB,
  type TestRunsTab,
} from '@/constants/test-run-schedules';
import { useSchedules } from './useSchedules';

const ORDER: TestRunsTab[] = [TEST_RUNS_TAB.RUNS, TEST_RUNS_TAB.SCHEDULES];

/** Runs | Schedules (n), where n counts every schedule in the project. */
export default function TestRunsTabs({
  value,
  onChange,
}: {
  value: TestRunsTab;
  onChange: (tab: TestRunsTab) => void;
}) {
  const schedules = useSchedules();
  const count = (schedules.data ?? []).length;
  const tabs = ORDER.map((key, index) => ({
    key,
    label:
      key === TEST_RUNS_TAB.SCHEDULES && count > 0
        ? `Schedules (${count})`
        : key === TEST_RUNS_TAB.SCHEDULES
          ? 'Schedules'
          : 'Runs',
    id: `test-runs-tab-${index}`,
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
