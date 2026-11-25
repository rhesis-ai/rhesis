'use client';

import { useState } from 'react';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import Link from 'next/link';
import dayjs from 'dayjs';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DocumentTitle from '@/components/common/DocumentTitle';
import AccessDenied from '@/components/common/AccessDenied';
import DetailTabNav from '@/components/common/DetailTabNav';
import { DetailTabPanel } from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import { can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { scheduleKeys } from '@/constants/query-keys';
import {
  PAUSED_REASON,
  SCHEDULE_STATUS,
  SCHEDULES_REFETCH_MS,
  TEST_RUNS_PARAM,
  TEST_RUNS_TAB,
} from '@/constants/test-run-schedules';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { is404ApiError } from '@/utils/api-client/is-not-found-error';
import { detailPageTitle } from '@/utils/document-title';
import ScheduleEditDrawer from '../../../components/schedules/ScheduleEditDrawer';
import ScheduleStatusChip from '../../../components/schedules/ScheduleStatusChip';
import TakeOverDialog from '../../../components/schedules/TakeOverDialog';
import { useScheduleActions } from '../../../components/schedules/useSchedules';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import ScheduleSummary, { RUNS_PER_PAGE } from './ScheduleSummary';
import ScheduleConfiguration from './ScheduleConfiguration';
import { TABS } from './tabs';
import { PAGE_HEADERS, directoryCrumb } from '@/constants/page-headers';

const SCHEDULES_HREF = `/test-runs?${TEST_RUNS_PARAM.TAB}=${TEST_RUNS_TAB.SCHEDULES}`;

interface Props {
  scheduleId: string;
}

export default function SchedulePageClient({ scheduleId }: Props) {
  const canRead = useCan(Capability.TestRun.READ);
  const actions = useScheduleActions();
  const [tab, setTab] = useState(0);
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState(false);
  const [takeOver, setTakeOver] = useState<TestRunSchedule | null>(null);

  const detail = useQuery({
    queryKey: [...scheduleKeys.detail(scheduleId), page],
    queryFn: () =>
      new ApiClientFactory()
        .getTestRunSchedulesClient()
        .get(scheduleId, RUNS_PER_PAGE, page * RUNS_PER_PAGE),
    placeholderData: keepPreviousData,
    refetchInterval: SCHEDULES_REFETCH_MS,
    retry: (count, error) => !is404ApiError(error) && count < 2,
    enabled: canRead,
  });

  if (!canRead) return <AccessDenied resource="test runs" />;

  const breadcrumbs = [
    directoryCrumb(PAGE_HEADERS.testRuns),
    { label: 'Schedules', href: SCHEDULES_HREF },
  ];

  if (detail.isError) {
    const deleted = is404ApiError(detail.error);
    return (
      <PageLayout title="Schedule" breadcrumbs={breadcrumbs}>
        <Alert severity={deleted ? 'info' : 'error'}>
          {deleted ? (
            <>
              This schedule was deleted. Its runs are still on the{' '}
              <Link href="/test-runs">Runs tab</Link>.
            </>
          ) : (
            'Could not load this schedule.'
          )}
        </Alert>
      </PageLayout>
    );
  }

  const schedule = detail.data;
  if (!schedule) {
    return (
      <PageLayout title="Schedule" breadcrumbs={breadcrumbs}>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      </PageLayout>
    );
  }

  const editable = can(schedule, Capability.TestRun.UPDATE);
  const paused = schedule.status === SCHEDULE_STATUS.PAUSED;
  const needsOwner =
    paused && schedule.paused_reason === PAUSED_REASON.CREATOR_ACCESS;

  const fabs = (
    <FabGroup>
      {can(schedule, Capability.TestRun.EXECUTE) && (
        <Fab
          icon={<PlayArrowIcon />}
          tooltip="Run now"
          onClick={() => actions.runNow(schedule)}
        />
      )}
      {editable && (
        <Fab
          icon={<EditIcon />}
          tooltip="Edit"
          onClick={() => setEditing(true)}
        />
      )}
      {editable && schedule.status === SCHEDULE_STATUS.SCHEDULED && (
        <Fab
          icon={<PauseIcon />}
          tooltip="Pause"
          onClick={() => actions.pause(schedule)}
        />
      )}
      {editable && paused && !needsOwner && (
        <Fab
          icon={<RestartAltIcon />}
          tooltip="Resume"
          onClick={() => actions.resume(schedule)}
        />
      )}
    </FabGroup>
  );

  const metadata = (
    <Box
      sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}
    >
      <DetailMetadataStrip
        items={[
          { label: 'created by:', value: schedule.owner?.name || '—' },
          {
            label: 'created on:',
            value: schedule.created_at
              ? dayjs(schedule.created_at).format('D MMM YYYY')
              : '—',
          },
        ]}
      />
      <ScheduleStatusChip schedule={schedule} />
    </Box>
  );

  return (
    <PageLayout
      title={schedule.name}
      breadcrumbs={[...breadcrumbs, { label: schedule.name }]}
      actions={fabs}
      metadata={metadata}
    >
      <DocumentTitle title={detailPageTitle(schedule.name, 'Schedules')} />
      <DetailTabNav
        tabs={TABS.map((t, index) => ({
          ...t,
          id: `schedule-tab-${index}`,
          'aria-controls': `schedule-tabpanel-${index}`,
        }))}
        activeIndex={tab}
        onChange={setTab}
        aria-label="Schedule sections"
      />
      <Box>
        <DetailTabPanel value={tab} index={0} prefix="schedule">
          <ScheduleSummary
            schedule={schedule}
            page={page}
            onPageChange={setPage}
            onTakeOver={() => setTakeOver(schedule)}
            loadingRuns={detail.isPlaceholderData}
          />
        </DetailTabPanel>
        <DetailTabPanel value={tab} index={1} prefix="schedule">
          <ScheduleConfiguration schedule={schedule} />
        </DetailTabPanel>
      </Box>
      {!editable && (
        <Typography variant="caption" color="text.secondary">
          You can see this schedule but not change it.
        </Typography>
      )}
      <ScheduleEditDrawer
        scheduleId={editing ? schedule.id : null}
        onClose={() => setEditing(false)}
        onTakeOver={setTakeOver}
      />
      <TakeOverDialog schedule={takeOver} onClose={() => setTakeOver(null)} />
    </PageLayout>
  );
}
