import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

// projects renders a grid of EntityCards, not a DataGrid, so the catch-all
// table skeleton would be the wrong shape here.
export default function ProjectsLoading() {
  return <PageCardGridSkeleton header={PAGE_HEADERS.projects} />;
}
