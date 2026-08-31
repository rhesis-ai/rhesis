import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import ExplorerClient from './ExplorerClient';
import { explorerList } from './components/list';

/**
 * Server component: fetches the first page of explorer sessions before
 * rendering so the page arrives with content already in place -- no
 * client-side spinner on first load.
 */
export default async function ExplorerPage() {
  const client = (await createServerApiFactory()).getExplorerClient();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Explorer.READ,
    () =>
      client.getExplorerTestSets(firstPageParams(explorerList))
  );

  return (
    <ExplorerClient
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}
