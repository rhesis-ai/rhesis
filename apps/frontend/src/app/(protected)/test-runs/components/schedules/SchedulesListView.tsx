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
import { formatRunTime } from '@/components/common/run-drawer/schedule-form';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import ScheduleRowActions from './ScheduleRowActions';
import ScheduleStatusChip from './ScheduleStatusChip';

interface Props {
  schedules: TestRunSchedule[];
  onOpen: (schedule: TestRunSchedule) => void;
  onTakeOver: (schedule: TestRunSchedule) => void;
  onDelete: (schedule: TestRunSchedule) => void;
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
          {schedules.map(schedule => (
            <TableRow
              key={schedule.id}
              hover
              sx={{ cursor: 'pointer' }}
              onClick={() => onOpen(schedule)}
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
                {schedule.next_run_at
                  ? formatRunTime(schedule.next_run_at, schedule.timezone)
                  : '—'}
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
