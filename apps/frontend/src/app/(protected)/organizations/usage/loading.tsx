import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Usage is a tabbed section page with no header FABs.
export default function UsageLoading() {
  return <PageDetailSkeleton actionCount={0} breadcrumbCount={0} />;
}
