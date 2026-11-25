import PageListSkeleton from '@/components/loading/PageListSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

export default function TestsLoading() {
  return <PageListSkeleton header={PAGE_HEADERS.tests} />;
}
