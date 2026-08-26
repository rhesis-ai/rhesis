import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
import type { Tool } from '@/utils/api-client/interfaces/tool';
import type { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import ToolsPageClient from './components/ToolsPageClient';

/**
 * Server component: fetches the tool connections (and the provider type
 * lookup the connection drawer needs) before rendering so the page arrives
 * with content already in place -- no client-side spinner on first load.
 * Fails open to "no initial data" so the client falls back to its own fetch.
 */
export default async function ToolsPage() {
  let initialData: Tool[] | undefined;
  let initialProviderTypes: TypeLookup[] | undefined;

  if (await hasServerCapability(Capability.Tool.READ)) {
    const factory = await createServerApiFactory();
    const [toolsResult, typesResult] = await Promise.allSettled([
      factory.getToolsClient().getTools({ limit: 100 }),
      factory.getTypeLookupClient().getTypeLookups({
        $filter: "type_name eq 'ToolProviderType'",
        limit: 100,
        sort_by: 'type_value',
        sort_order: 'asc',
      }),
    ]);

    if (toolsResult.status === 'fulfilled') {
      initialData = JSON.parse(JSON.stringify(toolsResult.value.data ?? []));
    }
    if (typesResult.status === 'fulfilled') {
      initialProviderTypes = JSON.parse(JSON.stringify(typesResult.value));
    }
  }

  return (
    <ToolsPageClient
      initialData={initialData}
      initialProviderTypes={initialProviderTypes}
    />
  );
}
