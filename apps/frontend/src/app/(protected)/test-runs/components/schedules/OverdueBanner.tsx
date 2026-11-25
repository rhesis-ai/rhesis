'use client';

import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';

/** Shown when runs are late: the scheduler hasn't started them. They start once it is back. */
export default function OverdueBanner({
  schedules,
  onView,
}: {
  schedules: TestRunSchedule[];
  /** One overdue schedule: open it. Several: show the list, overdue first. */
  onView: (overdue: TestRunSchedule[]) => void;
}) {
  const overdue = schedules.filter(s => s.overdue);
  if (overdue.length === 0) return null;
  const which =
    overdue.length === 1 ? overdue[0].name : `${overdue.length} schedules`;
  return (
    <Alert
      severity="warning"
      sx={{ mb: 2 }}
      action={
        <Button color="inherit" size="small" onClick={() => onView(overdue)}>
          View
        </Button>
      }
    >
      {which} should have started already. The scheduler may be down; runs less
      than an hour late still start once it is back, later ones are skipped and
      you are notified.
    </Alert>
  );
}
