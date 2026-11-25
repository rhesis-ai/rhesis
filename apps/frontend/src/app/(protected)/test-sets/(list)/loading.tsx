import PageListSkeleton from '@/components/loading/PageListSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

export default function TestSetsLoading() {
  return <PageListSkeleton header={PAGE_HEADERS.testSets} />;
}
