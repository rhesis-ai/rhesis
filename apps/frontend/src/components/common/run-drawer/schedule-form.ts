import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import type { ScheduleSpec } from '@/utils/api-client/interfaces/test-run-schedule';
import {
  SCHEDULE_NOTIFY,
  type ScheduleNotify,
} from '@/constants/test-run-schedules';

dayjs.extend(utc);
dayjs.extend(timezone);

/** The drawer's choices; turned into a ScheduleSpec by `toScheduleSpec`. The browser never parses cron. */
export const FREQUENCY = {
  HOURLY: 'hourly',
  DAILY: 'daily',
  WEEKDAYS: 'weekdays',
  WEEKLY: 'weekly',
  MONTHLY: 'monthly',
  CUSTOM: 'custom',
} as const;
export type Frequency = (typeof FREQUENCY)[keyof typeof FREQUENCY];

export const FREQUENCY_LABEL: Record<Frequency, string> = {
  hourly: 'Every hour',
  daily: 'Every day',
  weekdays: 'Every weekday',
  weekly: 'Every week on…',
  monthly: 'Every month on…',
  custom: 'Custom (cron)',
};

export const ENDS = { NEVER: 'never', ON: 'on', AFTER: 'after' } as const;
export type Ends = (typeof ENDS)[keyof typeof ENDS];

/** Cron day-of-week numbers, Monday first like the toggles. */
export const WEEKDAYS: { value: number; short: string; label: string }[] = [
  { value: 1, short: 'M', label: 'Monday' },
  { value: 2, short: 'T', label: 'Tuesday' },
  { value: 3, short: 'W', label: 'Wednesday' },
  { value: 4, short: 'T', label: 'Thursday' },
  { value: 5, short: 'F', label: 'Friday' },
  { value: 6, short: 'S', label: 'Saturday' },
  { value: 0, short: 'S', label: 'Sunday' },
];

export const LAST_DAY = 'L';
export const MONTH_DAYS = Array.from({ length: 28 }, (_, i) => String(i + 1));

export interface ScheduleForm {
  repeat: boolean;
  /** Run once: local date and time in `timezone`, as YYYY-MM-DD and HH:mm. */
  date: string;
  time: string;
  frequency: Frequency;
  days: number[];
  monthDay: string;
  minute: number;
  cron: string;
  timezone: string;
  ends: Ends;
  endsOn: string;
  maxRuns: number;
  notify: ScheduleNotify;
  name: string;
}

export const browserTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
};

export const timeZones = (): string[] => {
  try {
    return Intl.supportedValuesOf('timeZone');
  } catch {
    return ['UTC'];
  }
};

export function defaultScheduleForm(
  name = '',
  now: dayjs.Dayjs = dayjs(),
  zone = browserTimeZone()
): ScheduleForm {
  return {
    repeat: true,
    date: now.add(1, 'day').format('YYYY-MM-DD'),
    time: '09:00',
    frequency: FREQUENCY.WEEKDAYS,
    days: [now.day()],
    monthDay: '1',
    minute: 0,
    cron: '',
    timezone: zone,
    ends: ENDS.NEVER,
    endsOn: now.add(1, 'month').format('YYYY-MM-DD'),
    maxRuns: 10,
    notify: SCHEDULE_NOTIFY.PROBLEMS,
    name,
  };
}

/** The cron for a preset, at `HH:mm`. */
export function cronFor(form: ScheduleForm): string {
  const [hour, minute] = form.time.split(':').map(Number);
  switch (form.frequency) {
    case FREQUENCY.HOURLY:
      return `${form.minute} * * * *`;
    case FREQUENCY.DAILY:
      return `${minute} ${hour} * * *`;
    case FREQUENCY.WEEKDAYS:
      return `${minute} ${hour} * * 1-5`;
    case FREQUENCY.WEEKLY:
      return `${minute} ${hour} * * ${[...form.days].sort((a, b) => a - b).join(',')}`;
    case FREQUENCY.MONTHLY:
      return `${minute} ${hour} ${form.monthDay} * *`;
    default:
      return form.cron.trim();
  }
}

const localToUtc = (date: string, time: string, zone: string) =>
  dayjs.tz(`${date} ${time}`, 'YYYY-MM-DD HH:mm', zone).utc().toISOString();

/** Field problems the drawer shows under each field, before asking the server. */
export function formProblems(form: ScheduleForm, now: dayjs.Dayjs = dayjs()) {
  const problems: Partial<Record<keyof ScheduleForm, string>> = {};
  if (!form.repeat) {
    const at = dayjs.tz(
      `${form.date} ${form.time}`,
      'YYYY-MM-DD HH:mm',
      form.timezone
    );
    if (!at.isValid() || !at.isAfter(now))
      problems.time = 'Pick a time in the future';
  } else if (form.frequency === FREQUENCY.WEEKLY && form.days.length === 0) {
    problems.days = 'Pick at least one day';
  } else if (form.frequency === FREQUENCY.CUSTOM && !form.cron.trim()) {
    problems.cron = 'Enter a cron expression';
  }
  if (
    form.repeat &&
    form.ends === ENDS.ON &&
    !dayjs(form.endsOn).isAfter(now, 'day')
  ) {
    problems.endsOn = 'Enter a date after today';
  }
  if (form.repeat && form.ends === ENDS.AFTER && !(form.maxRuns >= 1)) {
    problems.maxRuns = 'Enter 1 or more';
  }
  return problems;
}

export function toScheduleSpec(form: ScheduleForm): ScheduleSpec {
  const repeating = form.repeat;
  return {
    // Blank: the backend names it after the test set.
    name: form.name.trim(),
    cron: repeating ? cronFor(form) : null,
    run_at: repeating ? null : localToUtc(form.date, form.time, form.timezone),
    timezone: form.timezone,
    ends_at:
      repeating && form.ends === ENDS.ON
        ? localToUtc(form.endsOn, '23:59', form.timezone)
        : null,
    max_runs: repeating && form.ends === ENDS.AFTER ? form.maxRuns : null,
    notify: form.notify,
  };
}

/** A run time in the viewer's zone, with the schedule's zone in brackets when they differ. */
export function formatRunTime(
  iso: string,
  scheduleZone: string,
  viewerZone = browserTimeZone()
) {
  const viewer = dayjs(iso).tz(viewerZone);
  const text = viewer.format('ddd D MMM, HH:mm');
  if (scheduleZone === viewerZone) return text;
  return `${text} (${dayjs(iso).tz(scheduleZone).format('HH:mm')} ${scheduleZone})`;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** Back from a stored schedule to the form. Only the drawer's own presets are recognised. */
export function fromSchedule(schedule: {
  name: string;
  cron: string | null;
  run_at: string | null;
  timezone: string;
  ends_at?: string | null;
  max_runs?: number | null;
  notify?: ScheduleNotify;
}): ScheduleForm {
  const zone = schedule.timezone || 'UTC';
  const form: ScheduleForm = {
    ...defaultScheduleForm(schedule.name, dayjs().tz(zone), zone),
    notify: schedule.notify ?? SCHEDULE_NOTIFY.PROBLEMS,
  };
  if (schedule.ends_at) {
    form.ends = ENDS.ON;
    form.endsOn = dayjs(schedule.ends_at).tz(zone).format('YYYY-MM-DD');
  } else if (schedule.max_runs) {
    form.ends = ENDS.AFTER;
    form.maxRuns = schedule.max_runs;
  }
  if (schedule.run_at) {
    const at = dayjs(schedule.run_at).tz(zone);
    return {
      ...form,
      repeat: false,
      date: at.format('YYYY-MM-DD'),
      time: at.format('HH:mm'),
    };
  }
  const cron = schedule.cron ?? '';
  const [minute, hour, dom, month, dow] = cron.split(' ');
  const custom = { ...form, frequency: FREQUENCY.CUSTOM, cron };
  if (!/^\d+$/.test(minute ?? '') || month !== '*') return custom;
  if (hour === '*' && dom === '*' && dow === '*') {
    return { ...form, frequency: FREQUENCY.HOURLY, minute: Number(minute) };
  }
  if (!/^\d+$/.test(hour ?? '')) return custom;
  const time = `${pad(Number(hour))}:${pad(Number(minute))}`;
  if (dom === '*' && dow === '*')
    return { ...form, frequency: FREQUENCY.DAILY, time };
  if (dom === '*' && dow === '1-5')
    return { ...form, frequency: FREQUENCY.WEEKDAYS, time };
  if (dom === '*' && /^\d(,\d)*$/.test(dow ?? '')) {
    return {
      ...form,
      frequency: FREQUENCY.WEEKLY,
      time,
      days: dow.split(',').map(Number),
    };
  }
  if (dow === '*' && (dom === LAST_DAY || MONTH_DAYS.includes(dom ?? ''))) {
    return { ...form, frequency: FREQUENCY.MONTHLY, time, monthDay: dom };
  }
  return custom;
}
