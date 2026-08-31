import { Metadata } from 'next';
import { Alert, Paper } from '@mui/material';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import TokensPageClient from './components/TokensPageClient';
import { tokensList } from './components/list';

export const metadata: Metadata = {
  title: 'API Tokens',
};

/**
 * Server component: fetches the first page of tokens before rendering so the
 * page arrives with content already in place -- no client-side spinner on
 * first load. See `prefetchList` for the permission-gating rationale.
 */
export default async function TokensPage() {
  const session = await auth();

  if (!session || session.error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          Authentication required. Please sign in to view API tokens.
        </Alert>
      </Paper>
    );
  }

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
