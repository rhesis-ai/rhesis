import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetch } from '@/utils/server-prefetch';
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
  const factory = await createServerApiFactory();
  const [initialData, initialProviderTypes] = await Promise.all([
    prefetch<Tool[]>(Capability.Tool.READ, async () => {
      const tools = await factory.getToolsClient().getTools({ limit: 100 });
      return tools.data ?? [];
    }),
    prefetch<TypeLookup[]>(Capability.Tool.READ, () =>
      factory.getTypeLookupClient().getTypeLookups({
        $filter: "type_name eq 'ToolProviderType'",
        limit: 100,
        sort_by: 'type_value',
        sort_order: 'asc',
      })
    ),
  ]);

  return (
    <ToolsPageClient
      initialData={initialData}
      initialProviderTypes={initialProviderTypes}
    />
  );
}
