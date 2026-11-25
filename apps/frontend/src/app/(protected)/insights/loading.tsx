import PageDashboardSkeleton from '@/components/loading/PageDashboardSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

// Insights is a dashboard: filter bar, pass-rate summary, requirement
// breakdown and per-requirement rows. Neither list shape fits it.
export default function InsightsLoading() {
  return <PageDashboardSkeleton header={PAGE_HEADERS.insights} />;
}
