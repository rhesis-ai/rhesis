import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import TokensPageClient from './components/TokensPageClient';
import { tokensList } from './components/list';
import { requireSession } from '@/utils/require-session';

export const metadata: Metadata = {
  title: 'API Tokens',
};

/**
 * Server component: fetches the first page of tokens before rendering so the
 * page arrives with content already in place -- no client-side spinner on
 * first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function TokensPage() {
  await requireSession();

  const factory = await createServerApiFactory();
  const { initialData, initialTotalCount } = await prefetchList(
    tokensList.capability,
    () => tokensList.list(factory, firstPageParams(tokensList))
  );

  return (
    <TokensPageClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}
