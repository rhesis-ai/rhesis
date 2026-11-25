import PageListSkeleton from '@/components/loading/PageListSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

export default function KnowledgeLoading() {
  return <PageListSkeleton header={PAGE_HEADERS.knowledge} showPills={false} />;
}
