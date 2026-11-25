import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { NAV_LABELS, REQUIREMENT_TAB_KEYS } from './components/tabs';

export default function RequirementDetailLoading() {
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.requirements)] }}
      // Every tab after Basic Information is a link list with a count badge.
      tabs={REQUIREMENT_TAB_KEYS.map(key =>
        key === 'basic'
          ? NAV_LABELS[key]
          : { label: NAV_LABELS[key], icon: true, badge: true }
      )}
    />
  );
}
