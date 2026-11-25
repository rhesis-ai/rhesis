'use client';

import Chip from '@mui/material/Chip';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import {
  PAUSED_REASON,
  PAUSED_REASON_LABEL,
  SCHEDULE_STATUS,
  SCHEDULE_STATUS_COLOR,
} from '@/constants/test-run-schedules';

/** Scheduled, Overdue, Paused (with why), Needs a new owner, or Finished. */
export default function ScheduleStatusChip({
  schedule,
}: {
  schedule: TestRunSchedule;
}) {
  if (schedule.overdue) {
    return <Chip size="small" color="warning" label="Overdue" />;
  }
  if (schedule.status === SCHEDULE_STATUS.PAUSED) {
    const reason = schedule.paused_reason ?? PAUSED_REASON.USER;
    const label =
      reason === PAUSED_REASON.USER || reason === PAUSED_REASON.CREATOR_ACCESS
        ? PAUSED_REASON_LABEL[reason]
        : 'Paused';
    return (
      <Chip
        size="small"
        color={reason === PAUSED_REASON.USER ? 'default' : 'warning'}
        label={label}
        title={PAUSED_REASON_LABEL[reason]}
      />
    );
  }
  const status = schedule.status ?? SCHEDULE_STATUS.SCHEDULED;
  return (
    <Chip size="small" color={SCHEDULE_STATUS_COLOR[status]} label={status} />
  );
}
