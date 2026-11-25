'use client';

import { Badge, Tab, Tabs } from '@mui/material';
import {
  TEST_RUNS_TAB,
  type TestRunsTab,
} from '@/constants/test-run-schedules';
import { useSchedules } from './useSchedules';

/** Runs | Schedules. The badge counts active schedules and turns orange when one is overdue. */
export default function TestRunsTabs({
  value,
  onChange,
}: {
  value: TestRunsTab;
  onChange: (tab: TestRunsTab) => void;
}) {
  const schedules = useSchedules();
  const items = schedules.data ?? [];
  const active = items.filter(s => s.status === 'Scheduled').length;
  const overdue = items.some(s => s.overdue);
  return (
    <Tabs
      value={value}
      onChange={(_, tab: TestRunsTab) => onChange(tab)}
      sx={{ mb: 2 }}
    >
      <Tab value={TEST_RUNS_TAB.RUNS} label="Runs" />
      <Tab
        value={TEST_RUNS_TAB.SCHEDULES}
        label={
          <Badge
            badgeContent={active}
            color={overdue ? 'warning' : 'primary'}
            sx={{ pr: active ? 1.5 : 0 }}
          >
            Schedules
          </Badge>
        }
      />
    </Tabs>
  );
}
