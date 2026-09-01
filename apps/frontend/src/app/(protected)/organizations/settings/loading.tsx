import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Organization settings is a tabbed section page with a 2-item breadcrumb
// trail and no header FABs.
export default function OrganizationSettingsLoading() {
  return <PageDetailSkeleton actionCount={0} breadcrumbCount={2} />;
}
