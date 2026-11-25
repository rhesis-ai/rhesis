import PageListSkeleton from '@/components/loading/PageListSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

export default function ExperimentsLoading() {
  return (
    <PageListSkeleton header={PAGE_HEADERS.experiments} showPills={false} />
  );
}
