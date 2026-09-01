import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';

// metrics renders a grid of EntityCards, not a DataGrid, so the catch-all
// table skeleton would be the wrong shape here.
export default function MetricsLoading() {
  return <PageCardGridSkeleton actionCount={1} />;
}
