import PageListSkeleton from '@/components/loading/PageListSkeleton';

// Redirects at once; without this the Endpoints/Tasks list header would show.
export default function NewEndpointLoading() {
  return <PageListSkeleton />;
}
