// Kept apart from SchedulePageClient so the route's loading view can draw the
// same tabs and trail without pulling the page in.

import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TEST_RUNS_PARAM, TEST_RUNS_TAB } from '@/constants/test-run-schedules';

export const TABS = [
  { key: 'summary', label: 'Summary' },
  { key: 'configuration', label: 'Configuration' },
];

const SCHEDULES_HREF = `/test-runs?${TEST_RUNS_PARAM.TAB}=${TEST_RUNS_TAB.SCHEDULES}`;

/** The trail before the schedule's own name. */
export const SCHEDULE_CRUMBS = [
  directoryCrumb(PAGE_HEADERS.testRuns),
  { label: 'Schedules', href: SCHEDULES_HREF },
];
