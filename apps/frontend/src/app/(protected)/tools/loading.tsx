import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';
import { PAGE_HEADERS } from '@/constants/page-headers';

// tools renders a grid of EntityCards, not a DataGrid. It is also the one card
// directory whose toolbar has no centred pill tabs, so the skeleton omits them
// rather than showing tabs that vanish when content arrives.
export default function ToolsLoading() {
  return <PageCardGridSkeleton header={PAGE_HEADERS.tools} showTabs={false} />;
}
