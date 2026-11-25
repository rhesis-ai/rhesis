import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';

export default function TaskDetailLoading() {
  return (
    <PageDetailSkeleton
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.tasks)] }}
    />
  );
}
