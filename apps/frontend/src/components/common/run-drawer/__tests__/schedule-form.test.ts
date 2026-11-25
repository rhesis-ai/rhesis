import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import {
  ENDS,
  FREQUENCY,
  cronFor,
  defaultScheduleForm,
  formProblems,
  formatRunTime,
  fromSchedule,
  toScheduleSpec,
} from '../schedule-form';

dayjs.extend(utc);
dayjs.extend(timezone);

const NOW = dayjs.tz('2026-11-25 10:00', 'Europe/Berlin');
const base = (overrides = {}) => ({
  ...defaultScheduleForm('', NOW, 'Europe/Berlin'),
  ...overrides,
});

describe('cronFor', () => {
  it.each([
    [FREQUENCY.HOURLY, { minute: 15 }, '15 * * * *'],
    [FREQUENCY.DAILY, {}, '0 9 * * *'],
    [FREQUENCY.WEEKDAYS, { time: '07:30' }, '30 7 * * 1-5'],
    [FREQUENCY.WEEKLY, { days: [4, 1] }, '0 9 * * 1,4'],
    [FREQUENCY.MONTHLY, { monthDay: 'L' }, '0 9 L * *'],
    [FREQUENCY.CUSTOM, { cron: ' 0 6 * * 0 ' }, '0 6 * * 0'],
  ])('%s', (frequency, overrides, cron) => {
    expect(cronFor(base({ frequency, ...overrides }))).toBe(cron);
  });
});

describe('toScheduleSpec', () => {
  it('converts a run-once date in the schedule zone to UTC', () => {
    const spec = toScheduleSpec(
      base({ repeat: false, date: '2026-11-26', time: '09:00' })
    );
    expect(spec.cron).toBeNull();
    expect(spec.run_at).toBe('2026-11-26T08:00:00.000Z');
  });

  it('leaves the name blank so the backend names it after the test set', () => {
    expect(toScheduleSpec(base()).name).toBe('');
  });

  it('sends ends only for the chosen kind', () => {
    expect(
      toScheduleSpec(base({ ends: ENDS.AFTER, maxRuns: 3 })).max_runs
    ).toBe(3);
    expect(toScheduleSpec(base({ ends: ENDS.NEVER })).ends_at).toBeNull();
  });
});

describe('formProblems', () => {
  it('asks for a future time when running once', () => {
    expect(
      formProblems(base({ repeat: false, date: '2026-11-24' }), NOW).time
    ).toBe('Pick a time in the future');
  });

  it('asks for at least one day on weekly', () => {
    expect(
      formProblems(base({ frequency: FREQUENCY.WEEKLY, days: [] }), NOW).days
    ).toBe('Pick at least one day');
  });

  it('has nothing to say about the defaults', () => {
    expect(formProblems(base(), NOW)).toEqual({});
  });
});

describe('formatRunTime', () => {
  it('adds the schedule zone in brackets when it differs', () => {
    expect(
      formatRunTime('2026-11-26T08:00:00Z', 'Europe/Berlin', 'Europe/London')
    ).toBe('Thu 26 Nov, 08:00 (09:00 Europe/Berlin)');
    expect(
      formatRunTime('2026-11-26T08:00:00Z', 'Europe/Berlin', 'Europe/Berlin')
    ).toBe('Thu 26 Nov, 09:00');
  });
});

describe('fromSchedule', () => {
  const stored = (cron: string) => ({
    name: 'S',
    cron,
    run_at: null,
    timezone: 'Europe/Berlin',
  });

  it.each([
    '15 * * * *',
    '0 9 * * *',
    '30 7 * * 1-5',
    '0 9 * * 1,4',
    '0 9 L * *',
    '0 9 12 * *',
  ])('round-trips the preset %s', cron => {
    expect(cronFor(fromSchedule(stored(cron)))).toBe(cron);
  });

  it('keeps anything else as custom cron', () => {
    const form = fromSchedule(stored('0 9-17/2 * * *'));
    expect(form.frequency).toBe(FREQUENCY.CUSTOM);
    expect(form.cron).toBe('0 9-17/2 * * *');
  });

  it('reads a run-once time in the schedule zone', () => {
    const form = fromSchedule({
      name: 'Once',
      cron: null,
      run_at: '2026-11-26T08:00:00Z',
      timezone: 'Europe/Berlin',
    });
    expect([form.repeat, form.date, form.time]).toEqual([
      false,
      '2026-11-26',
      '09:00',
    ]);
  });
});
