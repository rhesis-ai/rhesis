'use client';

import {
  Alert,
  Box,
  Button,
  Link as MuiLink,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import dayjs from 'dayjs';
import { SectionCard } from '@/components/common/SectionCard';
import ScheduleRow from './ScheduleRow';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  PAUSED_REASON,
  PAUSED_REASON_LABEL,
  SCHEDULE_NOTIFY_LABEL,
  SCHEDULE_STATUS,
} from '@/constants/test-run-schedules';
import {
  formatRunTime,
  timeUntil,
} from '@/components/common/run-drawer/schedule-form';
import {
  formatCost,
  formatDurationShort,
  formatTokenCount,
} from '@/utils/trace-utils';
import type {
  ScheduleRunSummary,
  TestRunScheduleDetail,
} from '@/utils/api-client/interfaces/test-run-schedule';
import { useScheduleActions } from '../../../components/schedules/useSchedules';

export const RUNS_PER_PAGE = 10;

/** Why a run was skipped, in words; the backend stores a short reason key. */
const SKIP_REASON: Record<string, string> = {
  quota: 'the organization reached its test execution limit',
  missed: 'the scheduler was unavailable',
  overlap: 'the previous run was still going',
  error: 'it could not be started',
};

interface Props {
  schedule: TestRunScheduleDetail;
  page: number;
  onPageChange: (page: number) => void;
  onTakeOver: () => void;
  loadingRuns: boolean;
}

const percent = (rate: number | null) =>
  rate === null ? '—' : `${Math.round(rate * 100)}%`;

const money = (usd: number | null | undefined) =>
  usd === null || usd === undefined ? '—' : formatCost(usd);

function Notices({
  schedule,
  onTakeOver,
}: {
  schedule: TestRunScheduleDetail;
  onTakeOver: () => void;
}) {
  const notices: React.ReactNode[] = [];
  const zone = schedule.timezone;
  if (schedule.overdue && schedule.next_run_at) {
    notices.push(
      <Alert severity="warning" key="overdue">
        Should have started at {formatRunTime(schedule.next_run_at, zone)}. The
        scheduler hasn&apos;t picked it up yet.
      </Alert>
    );
  }
  if (schedule.status === SCHEDULE_STATUS.PAUSED) {
    const reason = schedule.paused_reason ?? PAUSED_REASON.USER;
    const needsOwner = reason === PAUSED_REASON.CREATOR_ACCESS;
    notices.push(
      <Alert
        severity={reason === PAUSED_REASON.USER ? 'info' : 'warning'}
        key="paused"
        action={
          needsOwner &&
          can(schedule, Capability.TestRun.UPDATE) &&
          can(schedule, Capability.TestRun.EXECUTE) ? (
            <Button color="inherit" size="small" onClick={onTakeOver}>
              Take over
            </Button>
          ) : undefined
        }
      >
        {PAUSED_REASON_LABEL[reason]}
        {needsOwner && schedule.owner?.name
          ? `. ${schedule.owner.name} can no longer run tests here.`
          : '.'}
      </Alert>
    );
  }
  if (schedule.status === SCHEDULE_STATUS.FINISHED) {
    notices.push(
      <Alert severity="success" key="finished">
        Nothing else is planned. Edit it and pick a new date to run it again.
      </Alert>
    );
  }
  if (schedule.last_skip) {
    const why = SKIP_REASON[schedule.last_skip.reason];
    notices.push(
      <Alert severity="info" key="skip">
        The {formatRunTime(schedule.last_skip.at, zone)} run was skipped
        {why ? ` because ${why}` : ''}.
      </Alert>
    );
  }
  if (notices.length === 0) return null;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 3 }}>
      {notices}
    </Box>
  );
}

function PreviousRuns({
  schedule,
  page,
  onPageChange,
  loading,
}: {
  schedule: TestRunScheduleDetail;
  page: number;
  onPageChange: (page: number) => void;
  loading: boolean;
}) {
  const runs: ScheduleRunSummary[] = schedule.recent_runs;
  return (
    <SectionCard title="Previous runs from this schedule">
      {runs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No runs yet.
        </Typography>
      ) : (
        <TableContainer sx={{ opacity: loading ? 0.6 : 1 }}>
          <Table size="small" aria-label="Previous runs">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Started</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Pass rate</TableCell>
                <TableCell>Cost</TableCell>
                <TableCell>Duration</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {runs.map(run => (
                <TableRow key={run.id} hover>
                  <TableCell>
                    <MuiLink component={Link} href={`/test-runs/${run.id}`}>
                      {run.name || run.id}
                    </MuiLink>
                  </TableCell>
                  <TableCell>
                    {run.started_at
                      ? formatRunTime(run.started_at, schedule.timezone)
                      : '—'}
                  </TableCell>
                  <TableCell>{run.status ?? '—'}</TableCell>
                  <TableCell>{percent(run.pass_rate)}</TableCell>
                  <TableCell>{money(run.total_cost_usd)}</TableCell>
                  <TableCell>
                    {run.duration_s === null
                      ? '—'
                      : formatDurationShort(run.duration_s * 1000)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={schedule.usage.run_count}
            page={page}
            rowsPerPage={RUNS_PER_PAGE}
            rowsPerPageOptions={[RUNS_PER_PAGE]}
            onPageChange={(_, next) => onPageChange(next)}
          />
        </TableContainer>
      )}
    </SectionCard>
  );
}

export default function ScheduleSummary({
  schedule,
  page,
  onPageChange,
  onTakeOver,
  loadingRuns,
}: Props) {
  const actions = useScheduleActions();
  const zone = schedule.timezone;
  const usage = schedule.usage;
  const editable = can(schedule, Capability.TestRun.UPDATE);
  const next = schedule.next_run_at;

  return (
    <Box>
      <Notices schedule={schedule} onTakeOver={onTakeOver} />
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          columnGap: 3,
        }}
      >
        <SectionCard title="Next run">
          {next && schedule.status === SCHEDULE_STATUS.SCHEDULED ? (
            <>
              <Typography variant="h6">{formatRunTime(next, zone)}</Typography>
              <Typography variant="body2" color="text.secondary">
                {timeUntil(next)} · {zone}
              </Typography>
            </>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Nothing planned.
            </Typography>
          )}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Results, traces and annotations belong to each run. Open a run below
            to see them.
          </Typography>
        </SectionCard>

        <SectionCard title="Schedule">
          <ScheduleRow label="Repeats" value={schedule.repeats} />
          <ScheduleRow label="Runs as" value={schedule.owner?.name ?? '—'} />
          <ScheduleRow label="Time zone" value={zone} />
          <ScheduleRow
            label="Ends"
            value={
              schedule.ends_at
                ? formatRunTime(schedule.ends_at, zone)
                : schedule.max_runs
                  ? `After ${schedule.max_runs} runs`
                  : 'Never'
            }
          />
          <ScheduleRow
            label="Test set"
            value={
              schedule.test_set ? (
                <MuiLink
                  component={Link}
                  href={`/test-sets/${schedule.test_set.id}`}
                >
                  {schedule.test_set.name}
                </MuiLink>
              ) : (
                '—'
              )
            }
          />
          <ScheduleRow
            label="Endpoint"
            value={schedule.endpoint?.name ?? '—'}
          />
          <ScheduleRow
            label="Notify"
            value={SCHEDULE_NOTIFY_LABEL[schedule.notify]}
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Each run uses the tests in the set at the time it starts.
          </Typography>
        </SectionCard>

        <SectionCard title="Usage so far">
          {usage.run_count === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No runs yet.
            </Typography>
          ) : (
            <>
              <ScheduleRow
                label="Runs"
                value={
                  usage.first_run_at
                    ? `${usage.run_count} since ${dayjs(usage.first_run_at).format('D MMM')}`
                    : usage.run_count
                }
              />
              <ScheduleRow
                label="Total cost"
                value={`${money(usage.total_cost_usd)}${
                  usage.avg_cost_usd !== null
                    ? ` (${money(usage.avg_cost_usd)} per run)`
                    : ''
                }`}
              />
              <ScheduleRow
                label="Total tokens"
                value={`${formatTokenCount(usage.total_tokens)} (${formatTokenCount(
                  usage.input_tokens
                )} in, ${formatTokenCount(usage.output_tokens)} out)`}
              />
              {schedule.last_run && (
                <ScheduleRow
                  label="Last run"
                  value={`${schedule.last_run.name ?? ''} ${money(
                    schedule.last_run.total_cost_usd
                  )}`.trim()}
                />
              )}
              {usage.expected_month_usd !== null && (
                <ScheduleRow
                  label="Expected per month"
                  value={`≈ ${money(usage.expected_month_usd)}`}
                />
              )}
            </>
          )}
        </SectionCard>

        <SectionCard title="Upcoming runs">
          {schedule.upcoming.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Nothing planned.
            </Typography>
          ) : (
            <>
              {schedule.upcoming.map((at, index) => (
                <Box
                  key={at}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    py: 0.5,
                  }}
                >
                  <Typography variant="body2">
                    {formatRunTime(at, zone)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {index === 0 ? 'next' : timeUntil(at)}
                  </Typography>
                </Box>
              ))}
              {editable && Boolean(schedule.cron) && (
                <Button
                  size="small"
                  variant="outlined"
                  sx={{ mt: 1 }}
                  onClick={() => actions.skipNext(schedule)}
                >
                  Skip next run
                </Button>
              )}
            </>
          )}
        </SectionCard>
      </Box>

      <PreviousRuns
        schedule={schedule}
        page={page}
        onPageChange={onPageChange}
        loading={loadingRuns}
      />
    </Box>
  );
}
