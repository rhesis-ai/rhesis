import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';

// models renders a grid of EntityCards, not a DataGrid, so the catch-all
// table skeleton would be the wrong shape here.
export default function ModelsLoading() {
  return <PageCardGridSkeleton actionCount={2} />;
}
