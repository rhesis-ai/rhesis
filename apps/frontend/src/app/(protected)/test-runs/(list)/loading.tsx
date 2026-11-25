'use client';

import { useSearchParams } from 'next/navigation';
import PageListSkeleton from '@/components/loading/PageListSkeleton';
import { Capability } from '@/constants/capabilities';
import { PAGE_HEADERS } from '@/constants/page-headers';
import {
  TEST_RUNS_PARAM,
  TEST_RUNS_TAB,
  TEST_RUNS_TABS,
} from '@/constants/test-run-schedules';
import SchedulesTabSkeleton from '../components/schedules/SchedulesTabSkeleton';

// Runs | Schedules sit between the header and the body; the tab in the URL
// decides both the body and the header button (New Test Run or New schedule),
// as TestRunsPageClient does.
export default function TestRunsLoading() {
  const onSchedules =
    useSearchParams().get(TEST_RUNS_PARAM.TAB) === TEST_RUNS_TAB.SCHEDULES;
  const header = PAGE_HEADERS.testRuns;
  return (
    <PageListSkeleton
      header={{
        title: header.title,
        description: header.description,
        actions: [
          onSchedules ? Capability.TestRun.EXECUTE : Capability.TestRun.CREATE,
        ],
      }}
      tabs={TEST_RUNS_TABS.map(tab => tab.label)}
      activeTab={TEST_RUNS_TABS.findIndex(
        tab =>
          tab.key ===
          (onSchedules ? TEST_RUNS_TAB.SCHEDULES : TEST_RUNS_TAB.RUNS)
      )}
      body={onSchedules ? <SchedulesTabSkeleton /> : undefined}
    />
  );
}
