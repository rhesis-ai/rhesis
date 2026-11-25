import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import type {
  ScheduleOccurrence,
  TestRunSchedule,
} from '@/utils/api-client/interfaces/test-run-schedule';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

dayjs.extend(utc);
dayjs.extend(timezone);

/** What a card on the calendar stands for. */
export const CARD_KIND = {
  UPCOMING: 'upcoming',
  CHANGED: 'changed',
  OVERDUE: 'overdue',
  RUNNING: 'running',
  RAN: 'ran',
  FAILED: 'failed',
} as const;
export type CardKind = (typeof CARD_KIND)[keyof typeof CARD_KIND];

export const CARD_COLOR: Record<
  CardKind,
  'primary' | 'success' | 'error' | 'warning' | 'info'
> = {
  upcoming: 'primary',
  changed: 'primary',
  overdue: 'warning',
  running: 'info',
  ran: 'success',
  failed: 'error',
};

export const CARD_LABEL: Record<CardKind, string> = {
  upcoming: '',
  changed: 'Changed · this run only',
  overdue: 'Overdue',
  running: 'Running',
  ran: '',
  failed: 'Failed',
};

export interface WeekCard {
  key: string;
  kind: CardKind;
  scheduleId: string;
  name: string;
  /** When it runs, or ran. */
  at: string;
  /** The schedule's own time for this run, for edits. */
  original: string;
  runId?: string;
  passRate?: number | null;
}

export interface WeekDay {
  date: string;
  past: boolean;
  today: boolean;
  cards: WeekCard[];
}

export const weekStart = (anchor: dayjs.Dayjs) => {
  const day = anchor.startOf('day');
  // Monday first.
  return day.subtract((day.day() + 6) % 7, 'day');
};

const RUNNING = new Set(['Queued', 'Progress']);
const FAILED = new Set(['Failed', 'Partial']);

function runCard(run: TestRunDetail): WeekCard | null {
  const attributes = run.attributes ?? {};
  const scheduledFor =
    typeof attributes.scheduled_for === 'string'
      ? attributes.scheduled_for
      : null;
  const schedule = run.test_configuration?.attributes?.schedule as
    | { name?: string }
    | undefined;
  const scheduleId = run.test_configuration?.id;
  if (!scheduledFor || !scheduleId) return null;
  const status = run.status?.name ?? '';
  const kind = RUNNING.has(status)
    ? CARD_KIND.RUNNING
    : FAILED.has(status)
      ? CARD_KIND.FAILED
      : CARD_KIND.RAN;
  return {
    key: `run-${run.id}`,
    kind,
    scheduleId: String(scheduleId),
    name: schedule?.name ?? run.name ?? '',
    at: scheduledFor,
    original: scheduledFor,
    runId: String(run.id),
  };
}

/**
 * The week's cards: runs that happened (by `scheduled_for`), runs still planned, and runs
 * that should have started but didn't (overdue).
 */
export function buildWeek(
  start: dayjs.Dayjs,
  zone: string,
  occurrences: ScheduleOccurrence[],
  runs: TestRunDetail[],
  schedules: TestRunSchedule[],
  now: dayjs.Dayjs = dayjs()
): WeekDay[] {
  const cards: WeekCard[] = [];
  const ran = new Set<string>();
  runs.forEach(run => {
    const card = runCard(run);
    if (!card) return;
    cards.push(card);
    ran.add(`${card.scheduleId}|${dayjs(card.original).valueOf()}`);
  });
  occurrences.forEach(o => {
    if (ran.has(`${o.schedule_id}|${dayjs(o.occurrence).valueOf()}`)) return;
    cards.push({
      key: `occ-${o.schedule_id}-${o.occurrence}`,
      kind: o.changed ? CARD_KIND.CHANGED : CARD_KIND.UPCOMING,
      scheduleId: o.schedule_id,
      name: o.name,
      at: o.at,
      original: o.occurrence,
    });
  });
  schedules.forEach(s => {
    if (!s.overdue || !s.next_run_at) return;
    if (ran.has(`${s.id}|${dayjs(s.next_run_at).valueOf()}`)) return;
    cards.push({
      key: `overdue-${s.id}`,
      kind: CARD_KIND.OVERDUE,
      scheduleId: s.id,
      name: s.name,
      at: s.next_run_at,
      original: s.next_run_at,
    });
  });

  const today = now.tz(zone).format('YYYY-MM-DD');
  return Array.from({ length: 7 }, (_, i) => {
    const date = start.add(i, 'day').format('YYYY-MM-DD');
    return {
      date,
      past: date < today,
      today: date === today,
      cards: cards
        .filter(card => dayjs(card.at).tz(zone).format('YYYY-MM-DD') === date)
        .sort((a, b) => dayjs(a.at).valueOf() - dayjs(b.at).valueOf()),
    };
  });
}
