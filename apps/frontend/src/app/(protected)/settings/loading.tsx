import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Settings stacks section cards straight under the header: no tab bar,
// no breadcrumbs and no header FABs.
export default function SettingsLoading() {
  return (
    <PageDetailSkeleton actionCount={0} breadcrumbCount={0} showTabs={false} />
  );
}
