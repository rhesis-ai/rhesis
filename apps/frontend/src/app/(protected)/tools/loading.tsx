import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';

// tools renders a grid of EntityCards, not a DataGrid. It is also the one card
// directory whose toolbar has no centred pill tabs, so the skeleton omits them
// rather than showing tabs that vanish when content arrives.
export default function ToolsLoading() {
  return <PageCardGridSkeleton actionCount={1} showTabs={false} />;
}
