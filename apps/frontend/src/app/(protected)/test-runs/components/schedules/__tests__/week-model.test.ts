import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import {
  CARD_KIND,
  buildWeek,
  cardCaption,
  dayAfter,
  weekStart,
  type WeekCard,
} from '../week-model';

dayjs.extend(utc);
dayjs.extend(timezone);

const ZONE = 'UTC';
const NOW = dayjs.tz('2026-11-25 12:00', ZONE); // a Wednesday
const START = weekStart(NOW);

const occ = (iso: string, changed = false, at = iso) => ({
  schedule_id: 's1',
  name: 'Daily',
  occurrence: iso,
  at,
  changed,
});

const run = (scheduledFor: string, status: string) =>
  ({
    id: `r-${scheduledFor}`,
    name: 'bright-otter',
    status: { name: status },
    attributes: { trigger: 'schedule', scheduled_for: scheduledFor },
    test_configuration: {
      id: 's1',
      attributes: { schedule: { name: 'Daily' } },
    },
  }) as unknown as TestRunDetail;

const kinds = (days: ReturnType<typeof buildWeek>, date: string) =>
  days.find(d => d.date === date)?.cards.map(c => c.kind);

describe('buildWeek', () => {
  it('starts on Monday', () => {
    expect(START.format('YYYY-MM-DD')).toBe('2026-11-23');
  });

  it('puts a run that happened on the slot it was scheduled for', () => {
    const days = buildWeek(
      START,
      ZONE,
      [],
      [
        run('2026-11-23T09:00:00Z', 'Completed'),
        run('2026-11-24T09:00:00Z', 'Failed'),
      ],
      [],
      NOW
    );
    expect(kinds(days, '2026-11-23')).toEqual(['ran']);
    expect(kinds(days, '2026-11-24')).toEqual(['failed']);
  });

  it('shows a planned run once, as the run when it already ran', () => {
    const days = buildWeek(
      START,
      ZONE,
      [
        occ('2026-11-26T09:00:00Z'),
        occ('2026-11-27T09:00:00Z', true, '2026-11-27T11:00:00Z'),
      ],
      [run('2026-11-26T09:00:00Z', 'Progress')],
      [],
      NOW
    );
    expect(kinds(days, '2026-11-26')).toEqual(['running']);
    expect(kinds(days, '2026-11-27')).toEqual(['changed']);
  });

  it('marks overdue schedules on their slot and past days as past', () => {
    const schedule = {
      id: 's2',
      name: 'Late',
      overdue: true,
      next_run_at: '2026-11-25T10:00:00Z',
    } as TestRunSchedule;
    const days = buildWeek(START, ZONE, [], [], [schedule], NOW);
    expect(kinds(days, '2026-11-25')).toEqual(['overdue']);
    expect(days.find(d => d.date === '2026-11-24')?.past).toBe(true);
    expect(days.find(d => d.date === '2026-11-25')?.today).toBe(true);
  });
});

describe('dayAfter', () => {
  it('lands on midnight across the autumn clock change', () => {
    const start = weekStart(dayjs.tz('2026-10-21 12:00', 'Europe/Berlin'));
    // Clocks go back on Sun 25 Oct; Mon 26 Oct 00:00 Berlin is 23:00 UTC.
    expect(dayAfter(start, 7, 'Europe/Berlin').utc().toISOString()).toBe(
      '2026-10-25T23:00:00.000Z'
    );
  });
});

describe('cardCaption', () => {
  const card = (overrides: Partial<WeekCard>): WeekCard => ({
    key: 'k',
    kind: CARD_KIND.UPCOMING,
    scheduleId: 's1',
    name: 'Daily',
    at: '2026-11-25T09:00:00Z',
    original: '2026-11-25T09:00:00Z',
    ...overrides,
  });
  it('shows the pass rate on a run that happened', () => {
    expect(
      cardCaption(card({ kind: CARD_KIND.RAN, passRate: 91.6 }), '09:00')
    ).toBe('09:00 · Ran · 92%');
  });
  it('shows only the time on a planned run', () => {
    expect(cardCaption(card({}), '09:00')).toBe('09:00');
  });
});
