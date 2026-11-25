import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TABS } from './components/tabs';

export default function ScheduleDetailLoading() {
  return (
    <PageDetailSkeleton
      breadcrumbCount={3}
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.testRuns)] }}
      tabs={TABS.map(tab => tab.label)}
    />
  );
}
