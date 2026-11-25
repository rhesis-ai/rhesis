'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { ScheduleForm } from '@/components/common/run-drawer/schedule-form';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import OverdueBanner from './OverdueBanner';
import ScheduleCreateDrawer from './ScheduleCreateDrawer';
import ScheduleEditDrawer, { type OccurrenceRef } from './ScheduleEditDrawer';
import ScheduleScopeDialog from './ScheduleScopeDialog';
import SchedulesListView from './SchedulesListView';
import SchedulesWeekView from './SchedulesWeekView';
import TakeOverDialog from './TakeOverDialog';
import { useScheduleActions, useSchedules } from './useSchedules';

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
  onMoreOptions: (form: ScheduleForm) => void;
  /** A day picked on the calendar: open the create drawer on it. */
  onCreateOnDay: (date: string) => void;
}

type View = 'week' | 'list';
const VIEW_KEY = 'rhesis.schedules.view';

/** Week or list, remembered per viewer. Storage can be missing or blocked. */
function useRememberedView(): [View, (view: View) => void] {
  const [view, setView] = useState<View>('week');
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(VIEW_KEY);
      if (saved === 'week' || saved === 'list') setView(saved);
    } catch {
      // Private mode or blocked storage: keep the default.
    }
  }, []);
  const remember = (next: View) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_KEY, next);
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
}: Props) {
  const [view, setView] = useRememberedView();
  const canCreate = useCan(Capability.TestRun.EXECUTE);
  const schedules = useSchedules();
  const actions = useScheduleActions();
  const [takeOver, setTakeOver] = useState<TestRunSchedule | null>(null);
  const [deleting, setDeleting] = useState<TestRunSchedule | null>(null);
  const items = schedules.data ?? [];

  const viewToggle = (
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
  );

  return (
    <Box>
      <OverdueBanner schedules={items} />
      {view === 'list' && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1.5 }}>
          {viewToggle}
        </Box>
      )}
      {schedules.isLoading ? (
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
      <TakeOverDialog schedule={takeOver} onClose={() => setTakeOver(null)} />
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
    </Box>
  );
}
