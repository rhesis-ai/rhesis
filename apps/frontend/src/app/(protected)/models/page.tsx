import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { PROVIDER_TYPE_LOOKUP_FILTER } from '@/constants/model-types';
import ModelsPageClient, {
  type ModelsPageInitialData,
} from './components/ModelsPageClient';

/**
 * Server component: fetches the models plus the lookups the cards and drawers
 * need on first paint (provider types, user settings, statuses) so the page
 * arrives with content already in place -- no client-side spinner on first
 * load. Fails open to "no initial data" so the client falls back to its own
 * fetch.
 */
export default async function ModelsPage() {
  const initialData = await prefetch<ModelsPageInitialData>(
    Capability.Model.READ,
    async () => {
      const factory = await createServerApiFactory();
      const [models, providerTypes, userSettings, statuses] = await Promise.all(
        [
          factory.getModelsClient().getModels(),
          factory.getTypeLookupClient().getTypeLookups({
            $filter: PROVIDER_TYPE_LOOKUP_FILTER,
            limit: 100,
          }),
          factory
            .getUsersClient()
            .getUserSettings()
            .catch(() => null),
          factory
            .getStatusClient()
            .getStatuses({
              sort_by: 'name',
              sort_order: 'asc',
              entity_type: 'Model',
            })
            .catch(() => null),
        ]
      );

      return {
        models: models.data,
        providerTypes,
        userSettings,
        statuses,
      };
    }
  );

  return <ModelsPageClient initialData={initialData} />;
}
