import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';

export default function ScheduleDetailLoading() {
  return (
    <PageDetailSkeleton
      breadcrumbCount={3}
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.testRuns)] }}
    />
  );
}
