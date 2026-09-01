import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Usage is a tabbed section page with a 2-item breadcrumb trail and no
// header FABs.
export default function UsageLoading() {
  return <PageDetailSkeleton actionCount={0} breadcrumbCount={2} />;
}
