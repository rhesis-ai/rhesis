import { fireEvent, render, screen } from '@testing-library/react';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import ScheduleStatusChip from '../ScheduleStatusChip';
import SchedulesListView, { sortSchedules } from '../SchedulesListView';
import { scheduleOf } from '../../RunNameCell';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('../useSchedules', () => ({
  useScheduleActions: () => ({
    pause: jest.fn(),
    resume: jest.fn(),
    skipNext: jest.fn(),
    runNow: jest.fn(),
  }),
}));

const schedule = (
  overrides: Partial<TestRunSchedule> = {}
): TestRunSchedule => ({
  id: 's1',
  name: 'Weekday regression',
  status: 'Scheduled',
  overdue: false,
  repeats: 'Every weekday at 09:00',
  cron: '0 9 * * 1-5',
  run_at: null,
  timezone: 'UTC',
  next_run_at: '2026-11-26T09:00:00Z',
  ends_at: null,
  max_runs: null,
  notify: 'problems',
  paused_reason: null,
  last_skip: null,
  test_set: { id: 't1', name: 'Smoke set' },
  endpoint: { id: 'e1', name: 'Prod', connection_type: 'REST' },
  owner: { id: 'u1', name: 'Alex Morgan' },
  user_id: 'u1',
  created_at: null,
  last_run: null,
  permitted_actions: [],
  ...overrides,
});

describe('ScheduleStatusChip', () => {
  it.each([
    [{}, 'Scheduled'],
    [{ overdue: true }, 'Overdue'],
    [{ status: 'Paused' as const, paused_reason: 'user' as const }, 'Paused'],
    [
      { status: 'Paused' as const, paused_reason: 'creator_access' as const },
      'Needs a new owner',
    ],
    [{ status: 'Finished' as const }, 'Finished'],
  ])('%o reads %s', (overrides, label) => {
    render(<ScheduleStatusChip schedule={schedule(overrides)} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe('SchedulesListView', () => {
  const handlers = {
    onOpen: jest.fn(),
    onTakeOver: jest.fn(),
    onDelete: jest.fn(),
  };

  it('shows the plain-words timing, never the cron', () => {
    render(<SchedulesListView schedules={[schedule()]} {...handlers} />);
    expect(screen.getByText('Every weekday at 09:00')).toBeInTheDocument();
    expect(screen.queryByText('0 9 * * 1-5')).not.toBeInTheDocument();
    expect(screen.getByText('Not run yet')).toBeInTheDocument();
  });

  it('offers Take over instead of Resume when the owner lost access', () => {
    render(
      <SchedulesListView
        schedules={[
          schedule({ status: 'Paused', paused_reason: 'creator_access' }),
        ]}
        {...handlers}
      />
    );
    fireEvent.click(screen.getByLabelText('Actions for Weekday regression'));
    expect(screen.getByText('Take over')).toBeInTheDocument();
    expect(screen.queryByText('Resume')).not.toBeInTheDocument();
  });

  it('has an empty state', () => {
    render(<SchedulesListView schedules={[]} {...handlers} />);
    expect(screen.getByText('No schedules yet')).toBeInTheDocument();
  });
});

describe('scheduleOf', () => {
  const run = (attributes: Record<string, unknown>, schedule?: unknown) =>
    ({
      attributes,
      test_configuration: {
        id: 'c1',
        attributes: schedule ? { schedule } : {},
      },
    }) as unknown as TestRunDetail;

  it('names the schedule of a scheduled run', () => {
    expect(
      scheduleOf(run({ trigger: 'schedule' }, { name: 'Nightly' }))
    ).toEqual({
      id: 'c1',
      name: 'Nightly',
    });
  });

  it('is empty for manual runs and deleted schedules', () => {
    expect(scheduleOf(run({}, { name: 'Nightly' }))).toBeNull();
    expect(scheduleOf(run({ trigger: 'schedule' }))).toBeNull();
  });
});

describe('sortSchedules', () => {
  it('puts overdue first and paused and finished last', () => {
    const sorted = sortSchedules([
      schedule({ id: 'f', name: 'F', status: 'Finished', next_run_at: null }),
      schedule({ id: 'p', name: 'P', status: 'Paused' }),
      schedule({ id: 'b', name: 'B', next_run_at: '2026-11-27T09:00:00Z' }),
      schedule({ id: 'a', name: 'A', next_run_at: '2026-11-26T09:00:00Z' }),
      schedule({ id: 'o', name: 'O', overdue: true }),
    ]);
    expect(sorted.map(s => s.id)).toEqual(['o', 'a', 'b', 'p', 'f']);
  });
});
