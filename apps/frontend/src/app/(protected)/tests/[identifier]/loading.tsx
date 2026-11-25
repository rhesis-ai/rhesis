import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_KEYS, TAB_LABELS } from './components/tabs';

export default function TestDetailLoading() {
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.tests)] }}
      // Test Sets carries an icon before the label.
      tabs={TAB_KEYS.map(key => ({
        label: TAB_LABELS[key],
        icon: key === 'linked',
      }))}
    />
  );
}
