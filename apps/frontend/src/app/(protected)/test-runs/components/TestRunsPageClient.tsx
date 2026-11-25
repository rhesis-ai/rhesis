'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useBulkActionsBridge } from '@/hooks/useBulkActionsBridge';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import TestRunsGrid from './TestRunsGrid';
import RunDrawer from '@/components/common/RunDrawer';
import { testRunsList } from './list';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { rem } from '@/styles/theme-constants';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  TEST_RUNS_PARAM,
  TEST_RUNS_TAB,
  type TestRunsTab,
} from '@/constants/test-run-schedules';
import type { ScheduleForm } from '@/components/common/run-drawer/schedule-form';
import TestRunsTabs from './schedules/TestRunsTabs';
import SchedulesTab from './schedules/SchedulesTab';
import type { OccurrenceRef } from './schedules/ScheduleEditDrawer';

interface TestRunsPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: TestRunDetail[];
  initialTotalCount?: number;
}

export default function TestRunsPageClient({
  initialData,
  initialTotalCount = 0,
}: TestRunsPageClientProps) {
  const gate = useListAuthGate(testRunsList);
  const canCreateTestRun = useCan(Capability.TestRun.CREATE);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const { bulkActionsVisible, onBulkDelete, handleBulkActionsChange } =
    useBulkActionsBridge();
  const canSchedule = useCan(Capability.TestRun.EXECUTE);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tab: TestRunsTab =
    searchParams.get(TEST_RUNS_PARAM.TAB) === TEST_RUNS_TAB.SCHEDULES
      ? TEST_RUNS_TAB.SCHEDULES
      : TEST_RUNS_TAB.RUNS;
  const openScheduleId = searchParams.get(TEST_RUNS_PARAM.SCHEDULE);
  const occurrenceParam = searchParams.get(TEST_RUNS_PARAM.OCCURRENCE);
  const openOccurrence: OccurrenceRef | null = React.useMemo(() => {
    if (!occurrenceParam) return null;
    const [original, at] = occurrenceParam.split('|');
    return { original, at: at || original };
  }, [occurrenceParam]);
  const [scheduleCreate, setScheduleCreate] = React.useState<{
    open: boolean;
    date: string | null;
  }>({ open: false, date: null });
  const [scheduleSeed, setScheduleSeed] = React.useState<ScheduleForm | null>(
    null
  );

  // Tab, open schedule and open run live in the URL, so Back works and links can open them.
  const setParams = React.useCallback(
    (changes: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      Object.entries(changes).forEach(([key, value]) =>
        value === null ? next.delete(key) : next.set(key, value)
      );
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [router, pathname, searchParams]
  );
  const openSchedule = React.useCallback(
    (id: string | null, occurrence?: OccurrenceRef | null) =>
      setParams({
        [TEST_RUNS_PARAM.TAB]: TEST_RUNS_TAB.SCHEDULES,
        [TEST_RUNS_PARAM.SCHEDULE]: id,
        [TEST_RUNS_PARAM.OCCURRENCE]:
          id && occurrence ? `${occurrence.original}|${occurrence.at}` : null,
      }),
    [setParams]
  );

  useDocumentTitle('Test Runs');

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setRefreshTrigger(prev => prev + 1);
  }, []);

  if (!gate.ready) return gate.node;

  return (
    <>
      <PageLayout
        title="Test Runs"
        description="Executions of your test sets against AI endpoints. Track status, results, and history of each run."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            {bulkActionsVisible && (
              <Can capability={Capability.TestRun.DELETE}>
                <Fab
                  icon={<DeleteOutlineIcon sx={{ fontSize: rem(28) }} />}
                  tooltip="Delete Test Runs"
                  aria-label="Delete Test Runs"
                  onClick={onBulkDelete}
                  sx={{
                    bgcolor: 'error.main',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                />
              </Can>
            )}
            {tab === TEST_RUNS_TAB.SCHEDULES ? (
              canSchedule && (
                <Fab
                  icon={<FabAddIcon />}
                  tooltip="New schedule"
                  aria-label="New schedule"
                  onClick={() => setScheduleCreate({ open: true, date: null })}
                />
              )
            ) : (
              <Can capability={Capability.TestRun.CREATE}>
                <Fab
                  icon={<FabAddIcon />}
                  tooltip="New Test Run"
                  aria-label="New Test Run"
                  onClick={() => setCreateDrawerOpen(true)}
                />
              </Can>
            )}
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          <TestRunsTabs
            value={tab}
            onChange={next =>
              setParams({
                [TEST_RUNS_PARAM.TAB]:
                  next === TEST_RUNS_TAB.SCHEDULES ? next : null,
                [TEST_RUNS_PARAM.SCHEDULE]: null,
                [TEST_RUNS_PARAM.OCCURRENCE]: null,
              })
            }
          />
          {tab === TEST_RUNS_TAB.SCHEDULES ? (
            <SchedulesTab
              openScheduleId={openScheduleId}
              openOccurrence={openOccurrence}
              onOpenSchedule={openSchedule}
              createOpen={scheduleCreate.open}
              createDate={scheduleCreate.date}
              onCreateClose={() =>
                setScheduleCreate({ open: false, date: null })
              }
              onCreateOnDay={date => setScheduleCreate({ open: true, date })}
              onMoreOptions={form => {
                setScheduleCreate({ open: false, date: null });
                setScheduleSeed(form);
              }}
            />
          ) : (
            <TestRunsGrid
              canCreate={canCreateTestRun}
              onCreateClick={() => setCreateDrawerOpen(true)}
              onBulkActionsChange={handleBulkActionsChange}
              refreshTrigger={refreshTrigger}
              initialData={initialData}
              initialTotalCount={initialTotalCount}
            />
          )}
        </Box>
      </PageLayout>

      <RunDrawer
        mode="newTestRun"
        open={createDrawerOpen || scheduleSeed !== null}
        initialSchedule={scheduleSeed !== null}
        scheduleSeed={scheduleSeed ?? undefined}
        onClose={() => {
          setCreateDrawerOpen(false);
          setScheduleSeed(null);
        }}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}
