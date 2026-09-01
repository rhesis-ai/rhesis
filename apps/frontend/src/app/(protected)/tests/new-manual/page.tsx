import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { EntityType } from '@/types/entity-type';
import ManualTestWriter, {
  type ManualTestWriterInitialData,
} from './components/ManualTestWriter';

/**
 * Server component: fetches the requirement/topic/category dimensions the
 * table's autocompletes need so the form arrives with content already in
 * place -- no client-side spinner on first load. Fails open to "no initial
 * data" so the client falls back to its own fetch.
 */
export default async function NewTestPage() {
  await requireSession();

  let initialData: ManualTestWriterInitialData | undefined;

  try {
    const factory = await createServerApiFactory();
    const [requirements, topics, categories] = await Promise.all([
      factory.getRequirementClient().getRequirements({
        sort_by: 'name',
        sort_order: 'asc',
      }),
      factory.getTopicClient().getTopics({
        entity_type: EntityType.TEST,
        sort_by: 'name',
        sort_order: 'asc',
      }),
      factory.getCategoryClient().getCategories({
        entity_type: EntityType.TEST,
        sort_by: 'name',
        sort_order: 'asc',
      }),
    ]);

    initialData = {
      requirements: requirements.filter(
        b => b.id && b.name && b.name.trim() !== ''
      ),
      topics,
      categories,
    };
  } catch {
    // Fall back to the client fetch.
  }

  return <ManualTestWriter initialData={initialData} />;
}
