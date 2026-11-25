/** Schedules: states, settings and the words the UI shows for them. Mirrors the backend. */

export const SCHEDULE_STATUS = {
  SCHEDULED: 'Scheduled',
  PAUSED: 'Paused',
  FINISHED: 'Finished',
} as const;
export type ScheduleStatus =
  (typeof SCHEDULE_STATUS)[keyof typeof SCHEDULE_STATUS];

export const SCHEDULE_STATUS_COLOR: Record<
  ScheduleStatus,
  'primary' | 'default' | 'success'
> = {
  Scheduled: 'primary',
  Paused: 'default',
  Finished: 'success',
};

export const SCHEDULE_NOTIFY = {
  PROBLEMS: 'problems',
  ALWAYS: 'always',
  NEVER: 'never',
} as const;
export type ScheduleNotify =
  (typeof SCHEDULE_NOTIFY)[keyof typeof SCHEDULE_NOTIFY];

export const SCHEDULE_NOTIFY_LABEL: Record<ScheduleNotify, string> = {
  problems: 'When something goes wrong',
  always: 'After every run',
  never: 'Never',
};

export const SCHEDULE_SCOPE = {
  ONE: 'one',
  FOLLOWING: 'following',
} as const;
export type ScheduleScope =
  (typeof SCHEDULE_SCOPE)[keyof typeof SCHEDULE_SCOPE];

export const SCHEDULE_TRIGGER = {
  MANUAL: 'manual',
  SCHEDULE: 'schedule',
} as const;
export type ScheduleTrigger =
  (typeof SCHEDULE_TRIGGER)[keyof typeof SCHEDULE_TRIGGER];

export const PAUSED_REASON = {
  USER: 'user',
  CREATOR_ACCESS: 'creator_access',
  ENDPOINT_MISSING: 'endpoint_missing',
  TEST_SET_MISSING: 'test_set_missing',
  TEST_SET_EMPTY: 'test_set_empty',
  MODEL_UNAVAILABLE: 'model_unavailable',
  FAILURE_STREAK: 'failure_streak',
} as const;
export type PausedReason = (typeof PAUSED_REASON)[keyof typeof PAUSED_REASON];

export const PAUSED_REASON_LABEL: Record<PausedReason, string> = {
  user: 'Paused',
  creator_access: 'Needs a new owner',
  endpoint_missing: 'Paused: the endpoint was deleted',
  test_set_missing: 'Paused: the test set was deleted',
  test_set_empty: 'Paused: the test set has no tests',
  model_unavailable: "Paused: a model its runs need isn't available",
  failure_streak: 'Paused: the last 5 runs failed',
};

/** Notification event types a schedule sends; mirrors NotificationEventType.TestRunSchedule. */
export const SCHEDULE_NOTIFICATION = {
  PAUSED: 'test_run_schedule.paused',
  MISSED: 'test_run_schedule.missed',
  SKIPPED: 'test_run_schedule.skipped',
  NEEDS_OWNER: 'test_run_schedule.needs_owner',
} as const;

/** Tabs and URL keys on the Test Runs page. */
export const TEST_RUNS_TAB = { RUNS: 'runs', SCHEDULES: 'schedules' } as const;
export type TestRunsTab = (typeof TEST_RUNS_TAB)[keyof typeof TEST_RUNS_TAB];
export const TEST_RUNS_PARAM = {
  TAB: 'tab',
  SCHEDULE: 'schedule',
  OCCURRENCE: 'occurrence',
  TEST_SET: 'test_set',
} as const;

export const scheduleLink = (scheduleId: string) =>
  `/test-runs?${TEST_RUNS_PARAM.TAB}=${TEST_RUNS_TAB.SCHEDULES}&${TEST_RUNS_PARAM.SCHEDULE}=${scheduleId}`;

/** The Schedules tab refetches this often while it is visible. */
export const SCHEDULES_REFETCH_MS = 60_000;
/** The calendar asks the API for at most this many days at once. */
export const SCHEDULE_WINDOW_DAYS = 42;
export const SCHEDULE_PREVIEW_DEBOUNCE_MS = 300;
