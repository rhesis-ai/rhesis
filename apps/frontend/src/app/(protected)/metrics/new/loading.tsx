import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';

// Without this file the fallback is metrics/loading.tsx, the card-grid
// directory skeleton — the wrong shape for a form, and now visible while the
// page awaits its models. The form stacks its sections straight under the
// header: a 2-segment trail, no header FABs and no tab bar.
export default function NewMetricLoading() {
  return (
    <PageDetailSkeleton actionCount={0} breadcrumbCount={2} showTabs={false} />
  );
}
