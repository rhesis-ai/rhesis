import PageDetailSkeleton from '@/components/loading/PageDetailSkeleton';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';

export default function SwaggerImportLoading() {
  return (
    <PageDetailSkeleton
      showTabs={false}
      header={{ crumbs: [directoryCrumb(PAGE_HEADERS.endpoints)] }}
    />
  );
}
