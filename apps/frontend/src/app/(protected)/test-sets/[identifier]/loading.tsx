import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_KEYS, TAB_LABELS } from './components/tabs';

export default function TestSetDetailLoading() {
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.testSets)] }}
      // Tests and Test Runs carry an icon before the label.
      tabs={TAB_KEYS.map(key => ({
        label: TAB_LABELS[key],
        icon: key === 'linked' || key === 'runs',
      }))}
    />
  );
}
