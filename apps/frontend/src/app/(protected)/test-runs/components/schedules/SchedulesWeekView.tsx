'use client';

import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  ButtonBase,
  IconButton,
  Link as MuiLink,
  Skeleton,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Link from 'next/link';
import dayjs from 'dayjs';
import { useQuery } from '@tanstack/react-query';
import { browserTimeZone } from '@/components/common/run-drawer/schedule-form';
import { scheduleKeys, testRunKeys } from '@/constants/query-keys';
import {
  SCHEDULE_TRIGGER,
  SCHEDULES_REFETCH_MS,
} from '@/constants/test-run-schedules';
import { BORDER_RADIUS } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import type { OccurrenceRef } from './ScheduleEditDrawer';
import {
  CARD_COLOR,
  CARD_KIND,
  CARD_LABEL,
  buildWeek,
  weekStart,
  type WeekCard,
} from './week-model';

/** Cards per day before the rest fold into "+N more". */
const VISIBLE_CARDS = 6;

interface Props {
  schedules: TestRunSchedule[];
  canCreate: boolean;
  onOpenRun: (scheduleId: string, occurrence: OccurrenceRef) => void;
  onCreateOnDay: (date: string) => void;
  onShowList: () => void;
}

function useWeekData(start: dayjs.Dayjs) {
  const from = start.utc().toISOString();
  const to = start.add(7, 'day').utc().toISOString();
  const occurrences = useQuery({
    queryKey: scheduleKeys.occurrences(from, to),
    queryFn: () =>
      new ApiClientFactory()
        .getTestRunSchedulesClient()
        .occurrences(new Date(from), new Date(to)),
    refetchInterval: SCHEDULES_REFETCH_MS,
  });
  // A run starts at most an hour after its time, so look a little past the week.
  const runsTo = start.add(7, 'day').add(1, 'hour').utc().toISOString();
  const runs = useQuery({
    queryKey: testRunKeys.list(`schedule|${from}|${runsTo}`),
    queryFn: () =>
      new ApiClientFactory().getTestRunsClient().getTestRuns({
        trigger: SCHEDULE_TRIGGER.SCHEDULE,
        filter: `created_at ge '${from}' and created_at lt '${runsTo}'`,
        // The API's page limit; a week rarely has more scheduled runs than this.
        limit: 100,
      }),
    refetchInterval: SCHEDULES_REFETCH_MS,
  });
  return { occurrences, runs };
}

function Card({
  card,
  zone,
  onOpenRun,
}: {
  card: WeekCard;
  zone: string;
  onOpenRun: Props['onOpenRun'];
}) {
  const color = CARD_COLOR[card.kind];
  const time = dayjs(card.at).tz(zone).format('HH:mm');
  const body = (
    <>
      <Typography variant="caption" color="text.secondary">
        {time}
        {CARD_LABEL[card.kind] ? ` · ${CARD_LABEL[card.kind]}` : ''}
      </Typography>
      <Typography variant="body2" noWrap>
        {card.name}
      </Typography>
    </>
  );
  const sx = {
    display: 'block',
    width: '100%',
    textAlign: 'left',
    borderLeft: 3,
    borderColor: `${color}.main`,
    borderRadius: BORDER_RADIUS.xs,
    bgcolor: 'background.paper',
    px: 1,
    py: 0.5,
    mb: 0.75,
    boxShadow: 1,
    ...(card.kind === CARD_KIND.CHANGED ? { borderStyle: 'dashed' } : {}),
  } as const;
  if (card.runId) {
    return (
      <Box
        component={Link}
        href={`/test-runs/${card.runId}`}
        sx={{ ...sx, color: 'inherit', textDecoration: 'none' }}
      >
        {body}
      </Box>
    );
  }
  return (
    <ButtonBase
      sx={sx}
      onClick={() =>
        onOpenRun(card.scheduleId, { original: card.original, at: card.at })
      }
      aria-label={`${card.name} at ${time}`}
    >
      <Box sx={{ width: '100%' }}>{body}</Box>
    </ButtonBase>
  );
}

export default function SchedulesWeekView({
  schedules,
  canCreate,
  onOpenRun,
  onCreateOnDay,
  onShowList,
}: Props) {
  const zone = useMemo(() => browserTimeZone(), []);
  const [anchor, setAnchor] = useState(() => dayjs().tz(zone));
  const start = weekStart(anchor);
  const { occurrences, runs } = useWeekData(start);
  const [expanded, setExpanded] = useState<string | null>(null);

  const days = useMemo(
    () =>
      buildWeek(
        start,
        zone,
        occurrences.data?.items ?? [],
        runs.data?.data ?? [],
        schedules
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- start is derived from anchor
    [anchor, zone, occurrences.data, runs.data, schedules]
  );
  const hourly = occurrences.data?.hourly ?? [];
  // Only planned runs gate the calendar: if past runs fail to load, it still shows what's planned.
  const loading = occurrences.isLoading;
  const end = start.add(6, 'day');

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <IconButton
          aria-label="Previous week"
          onClick={() => setAnchor(a => a.subtract(1, 'week'))}
        >
          <ChevronLeftIcon />
        </IconButton>
        <IconButton
          aria-label="Next week"
          onClick={() => setAnchor(a => a.add(1, 'week'))}
        >
          <ChevronRightIcon />
        </IconButton>
        <Button size="small" onClick={() => setAnchor(dayjs().tz(zone))}>
          Today
        </Button>
        <Typography variant="subtitle1">
          {start.format('D MMM')} – {end.format('D MMM YYYY')}
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ ml: 'auto' }}
        >
          Times in {zone}
        </Typography>
      </Box>

      {hourly.length > 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            mb: 1.5,
            px: 1.5,
            py: 1,
            border: 1,
            borderColor: 'divider',
            borderRadius: BORDER_RADIUS.sm,
          }}
        >
          <Typography variant="body2">
            Every hour: {hourly.map(h => h.name).join(', ')} (not drawn on each
            day)
          </Typography>
          <MuiLink
            component="button"
            variant="body2"
            onClick={onShowList}
            sx={{ ml: 'auto' }}
          >
            Show in list
          </MuiLink>
        </Box>
      )}

      <Box sx={{ overflowX: 'auto' }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, minmax(120px, 1fr))',
            gap: 1,
            minWidth: theme => theme.breakpoints.values.md,
          }}
        >
          {days.map(day => {
            const open = expanded === day.date;
            const shown = open ? day.cards : day.cards.slice(0, VISIBLE_CARDS);
            const hidden = day.cards.length - shown.length;
            return (
              <Box
                key={day.date}
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  minHeight: theme => theme.spacing(40),
                  p: 1,
                  borderRadius: BORDER_RADIUS.sm,
                  bgcolor: day.today ? 'action.selected' : 'action.hover',
                  opacity: day.past ? 0.75 : 1,
                  '&:hover .new-schedule, & .new-schedule:focus-visible': {
                    opacity: 1,
                  },
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ fontWeight: day.today ? 700 : 400, mb: 1 }}
                  color={day.today ? 'primary' : 'text.secondary'}
                >
                  {dayjs(day.date).format('ddd D')}
                </Typography>
                {loading ? (
                  <Skeleton variant="rounded" height={40} />
                ) : (
                  shown.map(card => (
                    <Card
                      key={card.key}
                      card={card}
                      zone={zone}
                      onOpenRun={onOpenRun}
                    />
                  ))
                )}
                {hidden > 0 && (
                  <MuiLink
                    component="button"
                    variant="caption"
                    onClick={() => setExpanded(day.date)}
                  >
                    +{hidden} more
                  </MuiLink>
                )}
                {canCreate && !day.past && (
                  <ButtonBase
                    className="new-schedule"
                    onClick={() => onCreateOnDay(day.date)}
                    sx={{
                      mt: 'auto',
                      flexGrow: day.cards.length === 0 ? 1 : 0,
                      minHeight: theme => theme.spacing(5),
                      opacity: 0,
                      transition: 'opacity 120ms',
                      border: 1,
                      borderStyle: 'dashed',
                      borderColor: 'divider',
                      borderRadius: BORDER_RADIUS.xs,
                      color: 'text.secondary',
                      typography: 'caption',
                    }}
                    aria-label={`New schedule on ${dayjs(day.date).format('dddd D MMMM')}`}
                  >
                    <AddIcon fontSize="small" /> New schedule
                  </ButtonBase>
                )}
              </Box>
            );
          })}
        </Box>
      </Box>
      {canCreate && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1 }}
        >
          Click a day to schedule a test set on it, or a run to change or skip
          it.
        </Typography>
      )}
      {!loading &&
        days.every(d => d.cards.length === 0) &&
        hourly.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Nothing is scheduled this week.
          </Typography>
        )}
    </Box>
  );
}
