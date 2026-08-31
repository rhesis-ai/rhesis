export const dynamic = 'force-dynamic';

import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import KnowledgeClientWrapper from './components/KnowledgeClientWrapper';
import { sourcesList } from './components/list';
import { requireSession } from '@/utils/require-session';

/**
 * Server component for the Knowledge page
 */
export default async function KnowledgePage() {
  await requireSession();

  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Source.READ,
    () => sourcesList.list(factory, firstPageParams(sourcesList))
  );

  return (
    <KnowledgeClientWrapper
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}
