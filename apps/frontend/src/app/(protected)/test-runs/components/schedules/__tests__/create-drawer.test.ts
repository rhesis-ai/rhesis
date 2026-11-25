import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { dayStart } from '../ScheduleCreateDrawer';

jest.mock('@/hooks/useEndpoints', () => ({ useEndpoints: () => ({}) }));
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));
jest.mock('../useSchedules', () => ({ useScheduleActions: () => ({}) }));

dayjs.extend(utc);
dayjs.extend(timezone);

describe('dayStart', () => {
  const now = dayjs.tz('2026-11-25 14:20', 'Europe/Berlin');
  it('keeps the default time on a later day', () => {
    expect(dayStart('2026-11-26', '09:00', 'Europe/Berlin', now)).toBe('09:00');
  });
  it('moves today to the next full hour once 09:00 has passed', () => {
    expect(dayStart('2026-11-25', '09:00', 'Europe/Berlin', now)).toBe('15:00');
  });
});
