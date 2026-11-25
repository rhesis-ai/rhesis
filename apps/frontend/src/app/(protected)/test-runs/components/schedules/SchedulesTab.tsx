'use client';

import { useMemo, useState, useSyncExternalStore } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { useCan } from '@/components/common/Can';
import {
  SkeletonSlot,
  useSkeletonMode,
} from '@/components/loading/SkeletonMode';
import { Capability } from '@/constants/capabilities';
import type { ScheduleForm } from '@/components/common/run-drawer/schedule-form';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import OverdueBanner from './OverdueBanner';
import ScheduleCreateDrawer, {
  type ScheduleTargets,
} from './ScheduleCreateDrawer';
import ScheduleEditDrawer, { type OccurrenceRef } from './ScheduleEditDrawer';
import ScheduleScopeDialog from './ScheduleScopeDialog';
import SchedulesListView from './SchedulesListView';
import SchedulesWeekView from './SchedulesWeekView';
import TakeOverDialog from './TakeOverDialog';
import { useScheduleActions, useSchedules } from './useSchedules';
import {
  readRememberedView,
  SCHEDULES_VIEW_KEY,
  type SchedulesView,
} from './schedules-view';

interface Props {
  /** Open schedule (drawer), from the URL. */
  openScheduleId: string | null;
  openOccurrence: OccurrenceRef | null;
  onOpenSchedule: (
    id: string | null,
    occurrence?: OccurrenceRef | null
  ) => void;
  createOpen: boolean;
  createDate: string | null;
  onCreateClose: () => void;
  onMoreOptions: (form: ScheduleForm, targets: ScheduleTargets) => void;
  /** Show only this test set's schedules, from the URL. */
  testSetId: string | null;
  onClearTestSet: () => void;
  /** A day picked on the calendar: open the create drawer on it. */
  onCreateOnDay: (date: string) => void;
}

type View = SchedulesView;

const subscribeNever = () => () => {};

/**
 * Week or list, remembered per viewer. Storage can be missing or blocked.
 * Read during render ('week' on the server), so the loading view and the page
 * open in the remembered view without first drawing the week.
 */
function useRememberedView(): [View, (view: View) => void] {
  const saved = useSyncExternalStore<View>(
    subscribeNever,
    () => readRememberedView() ?? 'week',
    () => 'week'
  );
  const [chosen, setChosen] = useState<View | null>(null);
  const view = chosen ?? saved;
  const remember = (next: View) => {
    setChosen(next);
    try {
      window.localStorage.setItem(SCHEDULES_VIEW_KEY, next);
    } catch {
      // Not remembered, still switched.
    }
  };
  return [view, remember];
}

export default function SchedulesTab({
  openScheduleId,
  openOccurrence,
  onOpenSchedule,
  createOpen,
  createDate,
  onCreateClose,
  onMoreOptions,
  onCreateOnDay,
  testSetId,
  onClearTestSet,
}: Props) {
  const [view, setView] = useRememberedView();
  const canCreate = useCan(Capability.TestRun.EXECUTE);
  // As a route's loading view: the views draw their own placeholders, no data.
  const skeleton = useSkeletonMode();
  const schedules = useSchedules(!skeleton);
  const actions = useScheduleActions();
  const [takeOver, setTakeOver] = useState<TestRunSchedule | null>(null);
  const [deleting, setDeleting] = useState<TestRunSchedule | null>(null);
  const all = useMemo(
    () => (skeleton ? [] : (schedules.data ?? [])),
    [skeleton, schedules.data]
  );
  const items = useMemo(
    () => (testSetId ? all.filter(s => s.test_set?.id === testSetId) : all),
    [all, testSetId]
  );
  const scheduleIds = useMemo(
    () => (testSetId ? new Set(items.map(s => s.id)) : null),
    [items, testSetId]
  );
  const testSetName =
    all.find(s => s.test_set?.id === testSetId)?.test_set?.name ??
    'this test set';

  const viewToggle = (
    <SkeletonSlot>
      <ToggleButtonGroup
        size="small"
        exclusive
        value={view}
        onChange={(_, next: View | null) => next && setView(next)}
        aria-label="Calendar or list"
      >
        <ToggleButton value="week">Week</ToggleButton>
        <ToggleButton value="list">List</ToggleButton>
      </ToggleButtonGroup>
    </SkeletonSlot>
  );

  return (
    <Box>
      <OverdueBanner
        schedules={items}
        onView={overdue =>
          overdue.length === 1 ? onOpenSchedule(overdue[0].id) : setView('list')
        }
      />
      {testSetId && (
        <SkeletonSlot sx={{ mb: 1.5 }}>
          <Chip
            label={`Test set: ${testSetName}`}
            onDelete={onClearTestSet}
            sx={{ mb: skeleton ? 0 : 1.5 }}
          />
        </SkeletonSlot>
      )}
      {view === 'list' && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1.5 }}>
          {viewToggle}
        </Box>
      )}
      {schedules.isLoading && !skeleton ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : view === 'week' ? (
        <SchedulesWeekView
          schedules={items}
          canCreate={canCreate}
          onOpenRun={(id, occurrence) => onOpenSchedule(id, occurrence)}
          onCreateOnDay={onCreateOnDay}
          onShowList={() => setView('list')}
          onOpenSchedule={id => onOpenSchedule(id)}
          scheduleIds={scheduleIds}
          viewToggle={viewToggle}
        />
      ) : (
        <SchedulesListView
          schedules={items}
          onOpen={schedule => onOpenSchedule(schedule.id)}
          onTakeOver={setTakeOver}
          onDelete={setDeleting}
        />
      )}

      {/* Drawers and dialogs follow the URL; the loading view leaves them to the page. */}
      {!skeleton && (
        <>
          <ScheduleEditDrawer
            scheduleId={openScheduleId}
            occurrence={openOccurrence}
            onClose={() => onOpenSchedule(null)}
            onTakeOver={setTakeOver}
          />
          <ScheduleCreateDrawer
            open={createOpen}
            initialDate={createDate}
            onClose={onCreateClose}
            onMoreOptions={onMoreOptions}
          />
          <TakeOverDialog
            schedule={takeOver}
            onClose={() => setTakeOver(null)}
          />
          <ScheduleScopeDialog
            open={Boolean(deleting)}
            title={`Delete ${deleting?.name ?? 'schedule'}?`}
            options={[
              {
                value: 'whole',
                label: 'The whole schedule',
                description: 'Nothing else will run. Its past runs are kept.',
              },
            ]}
            initial="whole"
            confirmText="Delete"
            destructive
            onCancel={() => setDeleting(null)}
            onConfirm={() => {
              if (deleting) void actions.remove(deleting);
              setDeleting(null);
            }}
          />
        </>
      )}
    </Box>
  );
}
