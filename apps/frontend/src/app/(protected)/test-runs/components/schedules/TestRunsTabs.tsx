'use client';

import DetailTabNav from '@/components/common/DetailTabNav';
import {
  TEST_RUNS_TAB,
  TEST_RUNS_TABS,
  type TestRunsTab,
} from '@/constants/test-run-schedules';
import { useSchedules } from './useSchedules';

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
  const tabs = TEST_RUNS_TABS.map(({ key, label }, index) => ({
    key,
    label:
      key === TEST_RUNS_TAB.SCHEDULES && count > 0
        ? `${label} (${count})`
        : label,
    id: `test-runs-tab-${index}`,
  }));
  return (
    <DetailTabNav
      tabs={tabs}
      activeIndex={TEST_RUNS_TABS.findIndex(tab => tab.key === value)}
      onChange={index => onChange(TEST_RUNS_TABS[index].key)}
      aria-label="Test runs sections"
      sx={{ mb: 3 }}
    />
  );
}
