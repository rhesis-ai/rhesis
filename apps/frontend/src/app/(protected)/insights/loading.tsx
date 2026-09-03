import PageDashboardSkeleton from '@/components/loading/PageDashboardSkeleton';

// Insights is a dashboard: filter bar, pass-rate summary, requirement
// breakdown and per-requirement rows. Neither list shape fits it.
export default function InsightsLoading() {
  return <PageDashboardSkeleton actionCount={2} />;
}
