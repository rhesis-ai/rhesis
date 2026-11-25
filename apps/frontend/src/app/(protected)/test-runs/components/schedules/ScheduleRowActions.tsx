'use client';

import { useState } from 'react';
import { IconButton, ListItemText, Menu, MenuItem } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { PAUSED_REASON, SCHEDULE_STATUS } from '@/constants/test-run-schedules';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import { useScheduleActions } from './useSchedules';

interface Props {
  schedule: TestRunSchedule;
  onEdit: () => void;
  onTakeOver: () => void;
  onDelete: () => void;
}

export default function ScheduleRowActions({
  schedule,
  onEdit,
  onTakeOver,
  onDelete,
}: Props) {
  const actions = useScheduleActions();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const canUpdate = can(schedule, Capability.TestRun.UPDATE);
  const canRun = can(schedule, Capability.TestRun.EXECUTE);
  const canDelete = can(schedule, Capability.TestRun.DELETE);
  const paused = schedule.status === SCHEDULE_STATUS.PAUSED;
  const needsOwner =
    paused && schedule.paused_reason === PAUSED_REASON.CREATOR_ACCESS;
  const scheduled = schedule.status === SCHEDULE_STATUS.SCHEDULED;

  const item = (label: string, onClick: () => void, show = true) =>
    show ? (
      <MenuItem
        key={label}
        onClick={() => {
          setAnchor(null);
          onClick();
        }}
      >
        <ListItemText>{label}</ListItemText>
      </MenuItem>
    ) : null;

  return (
    <>
      <IconButton
        size="small"
        aria-label={`Actions for ${schedule.name}`}
        onClick={event => {
          event.stopPropagation();
          setAnchor(event.currentTarget);
        }}
      >
        <MoreVertIcon fontSize="small" />
      </IconButton>
      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        onClick={event => event.stopPropagation()}
      >
        {item('Edit', onEdit, canUpdate)}
        {item('Run now', () => actions.runNow(schedule), canRun)}
        {item(
          'Skip next run',
          () => actions.skipNext(schedule),
          canUpdate && scheduled
        )}
        {item('Pause', () => actions.pause(schedule), canUpdate && scheduled)}
        {item(
          'Resume',
          () => actions.resume(schedule),
          canUpdate && paused && !needsOwner
        )}
        {item('Take over', onTakeOver, canUpdate && needsOwner)}
        {item('Delete', onDelete, canDelete)}
      </Menu>
    </>
  );
}
