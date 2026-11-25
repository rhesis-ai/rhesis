'use client';

import { useSyncExternalStore } from 'react';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import { skeletonTextSx } from '@/components/loading/skeletonText';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { readRememberedView, type SchedulesView } from './schedules-view';

/** The Schedules tab's geometry (SchedulesTab, SchedulesWeekView, SchedulesListView). */
const SCHEDULES = {
  /** Header row and toggle row: `gap: 1`, `mb: 1.5`. */
  rowGap: 1,
  rowMargin: 1.5,
  iconButton: 40,
  /** IconButton `edge="start"` pulls the first chevron left. */
  edgePull: '-12px',
  todayButton: { width: 64, height: 30 },
  rangeWidth: 172,
  zoneWidth: 148,
  toggle: { width: 112, height: 31 },
  /** 7 columns of at least 120px, `gap: 1`, no narrower than the md breakpoint. */
  dayMinWidth: '120px',
  /** A day cell: `minHeight: spacing(40)`, `p: 1`. */
  dayMinHeight: 40,
  dayPadding: 1,
  dayCaptionWidth: 44,
  entryHeight: 40,
  /** List view: a small table (Name, Status, Repeats, Next run, Last run,
   *  Test set, Endpoint, Owner). */
  listColumns: [
    { key: 'name', width: 120 },
    { key: 'status', width: 72 },
    { key: 'repeats', width: 96 },
    { key: 'next', width: 110 },
    { key: 'last', width: 110 },
    { key: 'test-set', width: 120 },
    { key: 'endpoint', width: 120 },
    { key: 'owner', width: 96 },
  ],
  listRows: 5,
  listRowHeight: 33,
} as const;

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
const LIST_ROWS = Array.from(
  { length: SCHEDULES.listRows },
  (_, i) => `row-${i}`
);

const subscribe = () => () => {};

/** The remembered view; 'week' on the server and until storage is read. */
function useSchedulesView(): SchedulesView {
  return useSyncExternalStore(
    subscribe,
    () => readRememberedView() ?? 'week',
    () => 'week'
  );
}

function Toggle() {
  return (
    <Skeleton
      variant="rounded"
      width={SCHEDULES.toggle.width}
      height={SCHEDULES.toggle.height}
      sx={{ flexShrink: 0 }}
    />
  );
}

function WeekSkeleton() {
  return (
    <>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: SCHEDULES.rowGap,
          mb: SCHEDULES.rowMargin,
        }}
      >
        <Skeleton
          variant="circular"
          width={SCHEDULES.iconButton}
          height={SCHEDULES.iconButton}
          sx={{ ml: SCHEDULES.edgePull }}
        />
        <Skeleton
          variant="circular"
          width={SCHEDULES.iconButton}
          height={SCHEDULES.iconButton}
        />
        <Skeleton
          variant="rounded"
          width={SCHEDULES.todayButton.width}
          height={SCHEDULES.todayButton.height}
        />
        <Skeleton
          variant="text"
          width={SCHEDULES.rangeWidth}
          sx={skeletonTextSx('bodyLReg')}
        />
        <Skeleton
          variant="text"
          width={SCHEDULES.zoneWidth}
          sx={{ ...skeletonTextSx('bodySReg'), ml: 'auto' }}
        />
        <Toggle />
      </Box>
      <Box sx={{ overflowX: 'auto' }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: `repeat(7, minmax(${SCHEDULES.dayMinWidth}, 1fr))`,
            gap: SCHEDULES.rowGap,
            minWidth: theme => theme.breakpoints.values.md,
          }}
        >
          {DAYS.map(day => (
            <Box
              key={day}
              sx={{
                minHeight: theme => theme.spacing(SCHEDULES.dayMinHeight),
                p: SCHEDULES.dayPadding,
                borderRadius: BORDER_RADIUS.sm,
                bgcolor: 'action.hover',
              }}
            >
              <Skeleton
                variant="text"
                width={SCHEDULES.dayCaptionWidth}
                sx={{ ...skeletonTextSx('bodySReg'), mb: 1 }}
              />
              <Skeleton variant="rounded" height={SCHEDULES.entryHeight} />
            </Box>
          ))}
        </Box>
      </Box>
    </>
  );
}

function ListSkeleton() {
  return (
    <>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          mb: SCHEDULES.rowMargin,
        }}
      >
        <Toggle />
      </Box>
      {['head', ...LIST_ROWS].map(row => (
        <Box
          key={row}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            height: SCHEDULES.listRowHeight,
            borderBottom: 1,
            borderColor: 'divider',
            px: 1,
          }}
        >
          {SCHEDULES.listColumns.map(column => (
            <Skeleton
              key={column.key}
              variant="text"
              width={column.width}
              sx={skeletonTextSx('bodyMReg')}
            />
          ))}
        </Box>
      ))}
    </>
  );
}

/** Placeholder for the Schedules tab, in the view this viewer last chose. */
export default function SchedulesTabSkeleton() {
  return useSchedulesView() === 'list' ? <ListSkeleton /> : <WeekSkeleton />;
}
