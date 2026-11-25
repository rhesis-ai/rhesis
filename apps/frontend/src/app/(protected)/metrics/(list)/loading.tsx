import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

// metrics renders a grid of EntityCards, not a DataGrid, so the catch-all
// table skeleton would be the wrong shape here.
export default function MetricsLoading() {
  return <PageCardGridSkeleton header={PAGE_HEADERS.metrics} />;
}
