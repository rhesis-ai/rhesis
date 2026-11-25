'use client';

import {
  Link as MuiLink,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import ScheduleIcon from '@mui/icons-material/Schedule';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import {
  formatRunTime,
  timeUntil,
} from '@/components/common/run-drawer/schedule-form';
import { SCHEDULE_STATUS } from '@/constants/test-run-schedules';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import ScheduleRowActions from './ScheduleRowActions';
import ScheduleStatusChip from './ScheduleStatusChip';

interface Props {
  schedules: TestRunSchedule[];
  onOpen: (schedule: TestRunSchedule) => void;
  onTakeOver: (schedule: TestRunSchedule) => void;
  onDelete: (schedule: TestRunSchedule) => void;
}

/** Overdue first, then by next run; paused and finished last. */
export function sortSchedules(schedules: TestRunSchedule[]): TestRunSchedule[] {
  const rank = (s: TestRunSchedule) =>
    s.overdue
      ? 0
      : s.status === SCHEDULE_STATUS.SCHEDULED
        ? 1
        : s.status === SCHEDULE_STATUS.PAUSED
          ? 2
          : 3;
  return [...schedules].sort(
    (a, b) =>
      rank(a) - rank(b) ||
      (a.next_run_at ?? '').localeCompare(b.next_run_at ?? '') ||
      a.name.localeCompare(b.name)
  );
}

const percent = (rate: number | null) =>
  rate === null ? '' : ` · ${Math.round(rate * 100)}%`;

export default function SchedulesListView({
  schedules,
  onOpen,
  onTakeOver,
  onDelete,
}: Props) {
  if (schedules.length === 0) {
    return (
      <SectionEmptyState
        icon={ScheduleIcon}
        title="No schedules yet"
        description="Schedule a test set to run it later or on a regular basis. Use + or pick Schedule run… in the run drawer."
      />
    );
  }
  return (
    <TableContainer>
      <Table size="small" aria-label="Schedules">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Repeats</TableCell>
            <TableCell>Next run</TableCell>
            <TableCell>Last run</TableCell>
            <TableCell>Test set</TableCell>
            <TableCell>Endpoint</TableCell>
            <TableCell>Owner</TableCell>
            <TableCell aria-label="Actions" />
          </TableRow>
        </TableHead>
        <TableBody>
          {sortSchedules(schedules).map(schedule => (
            <TableRow
              key={schedule.id}
              hover
              tabIndex={0}
              aria-label={`Open ${schedule.name}`}
              sx={{ cursor: 'pointer' }}
              onClick={() => onOpen(schedule)}
              onKeyDown={event => {
                if (
                  event.target === event.currentTarget &&
                  event.key === 'Enter'
                )
                  onOpen(schedule);
              }}
            >
              <TableCell>
                <MuiLink
                  component={Link}
                  href={`/test-runs/schedules/${schedule.id}`}
                  onClick={event => event.stopPropagation()}
                  underline="hover"
                >
                  {schedule.name}
                </MuiLink>
              </TableCell>
              <TableCell>
                <ScheduleStatusChip schedule={schedule} />
              </TableCell>
              <TableCell>{schedule.repeats}</TableCell>
              <TableCell>
                {schedule.next_run_at &&
                schedule.status === SCHEDULE_STATUS.SCHEDULED ? (
                  <>
                    {formatRunTime(schedule.next_run_at, schedule.timezone)}
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      component="div"
                    >
                      {schedule.overdue
                        ? 'Overdue'
                        : timeUntil(schedule.next_run_at)}
                    </Typography>
                  </>
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell>
                {schedule.last_run ? (
                  <MuiLink
                    component={Link}
                    href={`/test-runs/${schedule.last_run.id}`}
                    onClick={event => event.stopPropagation()}
                    underline="hover"
                  >
                    {schedule.last_run.name}
                    {percent(schedule.last_run.pass_rate)}
                  </MuiLink>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Not run yet
                  </Typography>
                )}
              </TableCell>
              <TableCell>{schedule.test_set?.name ?? '—'}</TableCell>
              <TableCell>{schedule.endpoint?.name ?? '—'}</TableCell>
              <TableCell>{schedule.owner?.name ?? '—'}</TableCell>
              <TableCell align="right">
                <ScheduleRowActions
                  schedule={schedule}
                  onEdit={() => onOpen(schedule)}
                  onTakeOver={() => onTakeOver(schedule)}
                  onDelete={() => onDelete(schedule)}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
