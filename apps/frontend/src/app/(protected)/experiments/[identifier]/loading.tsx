import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_KEYS, TAB_LABELS } from './components/tabs';

export default function ExperimentDetailLoading() {
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.experiments)] }}
      tabs={TAB_KEYS.map(key => TAB_LABELS[key])}
    />
  );
}
