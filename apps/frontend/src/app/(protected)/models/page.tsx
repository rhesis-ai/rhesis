import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
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
  let initialData: ModelsPageInitialData | undefined;

  if (await hasServerCapability(Capability.Model.READ)) {
    try {
      const factory = await createServerApiFactory();
      const [models, providerTypes, userSettings, statuses] = await Promise.all(
        [
          factory.getModelsClient().getModels(),
          factory.getTypeLookupClient().getTypeLookups({
            $filter: "type_name eq 'ProviderType'",
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

      initialData = JSON.parse(
        JSON.stringify({
          models: models.data,
          providerTypes,
          userSettings,
          statuses,
        } satisfies ModelsPageInitialData)
      );
    } catch {
      // Fall back to the client fetch.
    }
  }

  return <ModelsPageClient initialData={initialData} />;
}
