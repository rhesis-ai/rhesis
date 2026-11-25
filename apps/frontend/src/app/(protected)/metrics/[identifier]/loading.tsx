import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { NAV_LABELS } from './tabs';

export default function MetricDetailLoading() {
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.metrics)] }}
      // Tuning shows only for tunable metrics, which isn't known yet.
      tabs={[
        NAV_LABELS.basic,
        { label: NAV_LABELS['linked-requirements'], icon: true },
      ]}
    />
  );
}
