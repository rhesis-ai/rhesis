import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import {
  directoryCrumb,
  NEW_METRIC_CRUMB,
  PAGE_HEADERS,
} from '@/constants/page-headers';

// Without this file the fallback is metrics/loading.tsx, the card-grid
// directory skeleton — the wrong shape for a form, and now visible while the
// page awaits its models. The form stacks its sections straight under the
// header: a 2-segment trail, no header FABs and no tab bar. The trail is
// fixed and drawn at once; the title names the metric type, so it waits.
export default function NewMetricLoading() {
  return (
    <PageDetailSkeleton
      actionCount={0}
      breadcrumbCount={2}
      showTabs={false}
      header={{
        crumbs: [
          directoryCrumb(PAGE_HEADERS.metrics),
          { label: NEW_METRIC_CRUMB },
        ],
      }}
    />
  );
}
