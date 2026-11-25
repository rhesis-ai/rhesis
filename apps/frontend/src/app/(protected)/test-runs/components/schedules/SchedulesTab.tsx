'use client';

import { useState } from 'react';
import { Box, CircularProgress } from '@mui/material';
import type { ScheduleForm } from '@/components/common/run-drawer/schedule-form';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import OverdueBanner from './OverdueBanner';
import ScheduleCreateDrawer from './ScheduleCreateDrawer';
import ScheduleEditDrawer, { type OccurrenceRef } from './ScheduleEditDrawer';
import ScheduleScopeDialog from './ScheduleScopeDialog';
import SchedulesListView from './SchedulesListView';
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
}

export default function SchedulesTab({
  openScheduleId,
  openOccurrence,
  onOpenSchedule,
  createOpen,
  createDate,
  onCreateClose,
  onMoreOptions,
}: Props) {
  const schedules = useSchedules();
  const actions = useScheduleActions();
  const [takeOver, setTakeOver] = useState<TestRunSchedule | null>(null);
  const [deleting, setDeleting] = useState<TestRunSchedule | null>(null);
  const items = schedules.data ?? [];

  return (
    <Box>
      <OverdueBanner schedules={items} />
      {schedules.isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
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
