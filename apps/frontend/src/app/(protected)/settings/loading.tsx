import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Settings renders a 1-item breadcrumb trail and a tab bar over its section
// cards: no header FABs.
export default function SettingsLoading() {
  return <PageDetailSkeleton actionCount={0} breadcrumbCount={1} showTabs />;
}
