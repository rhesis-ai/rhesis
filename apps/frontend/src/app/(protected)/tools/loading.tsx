import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';

// tools renders a grid of EntityCards, not a DataGrid, so the catch-all
// table skeleton would be the wrong shape here.
export default function ToolsLoading() {
  return <PageCardGridSkeleton actionCount={1} />;
}
