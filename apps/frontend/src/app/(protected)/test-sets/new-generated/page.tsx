import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { Model } from '@/utils/api-client/interfaces/model';
import { Source } from '@/utils/api-client/interfaces/source';
import TestGenerationFlow from './components/TestGenerationFlow';

/**
 * Server component: prefetches the model/source dropdown data
 * TestInputScreen's selectors need so they open with content already in
 * place -- no client-side spinner. Fails open to "no initial data" so the
 * client falls back to its own fetch.
 */
export default async function GenerateTestsPage() {
  await requireSession();

  let initialModels: Model[] | undefined;
  let initialSources: Source[] | undefined;

  try {
    const factory = await createServerApiFactory();
    const [modelsResponse, sourcesResponse] = await Promise.all([
      factory.getModelsClient().getModels({
        sort_by: 'name',
        sort_order: 'asc',
        skip: 0,
        limit: 100,
      }),
      factory.getSourcesClient().getSources({ limit: 100, skip: 0 }),
    ]);
    initialModels = modelsResponse.data;
    initialSources = sourcesResponse.data;
  } catch {
    // Fall back to the client fetch.
  }

  return (
    <TestGenerationFlow
      initialModels={initialModels}
      initialSources={initialSources}
    />
  );
}
