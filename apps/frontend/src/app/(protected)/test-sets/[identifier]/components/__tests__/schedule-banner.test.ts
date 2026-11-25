import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import { bannerText } from '../TestSetScheduleBanner';

jest.mock('@/components/common/run-drawer/schedule-form', () => ({
  formatRunTime: (iso: string) => `at ${iso}`,
  timeUntil: () => 'soon',
}));

const schedule = (overrides: Partial<TestRunSchedule> = {}) =>
  ({
    id: 's1',
    name: 'Weekday regression',
    status: 'Scheduled',
    repeats: 'Every weekday at 09:00',
    timezone: 'Europe/Berlin',
    next_run_at: '2026-11-26T08:00:00Z',
    last_run: null,
    ...overrides,
  }) as TestRunSchedule;

describe('bannerText', () => {
  it('describes one schedule with its last pass rate', () => {
    const one = schedule({
      last_run: { pass_rate: 0.92 } as TestRunSchedule['last_run'],
    });
    expect(bannerText([one])).toBe(
      'Scheduled · Every weekday at 09:00 · Next run at 2026-11-26T08:00:00Z (soon) · Last run 92% pass'
    );
  });

  it('counts several schedules and picks the soonest run', () => {
    const later = schedule({ id: 's2', next_run_at: '2026-11-27T08:00:00Z' });
    expect(bannerText([later, schedule()])).toBe(
      '2 schedules · Next run at 2026-11-26T08:00:00Z (soon)'
    );
  });

  it('says paused when nothing is planned', () => {
    const paused = schedule({ status: 'Paused', next_run_at: null });
    expect(bannerText([paused])).toBe('Paused · Every weekday at 09:00');
  });
});
