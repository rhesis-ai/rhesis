import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import AnnotationsPageClient from './components/AnnotationsPageClient';
import { annotationsList } from './components/list';

/**
 * Server component: fetches the first page of annotations before rendering
 * so the page arrives with content already in place -- no client-side
 * spinner on first load. See `prefetchList` for the permission-gating
 * rationale.
 */
export default async function AnnotationsPage() {
  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    annotationsList.capability,
    () => annotationsList.list(factory, firstPageParams(annotationsList))
  );

  return (
    <AnnotationsPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}
