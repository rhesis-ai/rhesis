import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Settings renders a 1-item breadcrumb trail and stacks section cards straight
// under the header: no tab bar and no header FABs.
export default function SettingsLoading() {
  return (
    <PageDetailSkeleton actionCount={0} breadcrumbCount={1} showTabs={false} />
  );
}
