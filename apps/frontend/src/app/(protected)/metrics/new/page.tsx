import { redirect } from 'next/navigation';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { Model } from '@/utils/api-client/interfaces/model';
import NewMetricForm from './components/NewMetricForm';

interface NewMetricPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Server component: resolves the required `type` param (redirecting to
 * /metrics when it's missing, same as the old client-side effect) and
 * prefetches the evaluation models the form needs so the page arrives with
 * content already in place -- no client-side spinner on first load. Fails
 * open to "no initial data" so the client falls back to its own fetch.
 */
export default async function NewMetricPage({
  searchParams,
}: NewMetricPageProps) {
  await requireSession();

  const params = await searchParams;
  const type = typeof params.type === 'string' ? params.type : null;

  if (!type) {
    redirect('/metrics');
  }

  let initialModels: Model[] | undefined;

  try {
    const factory = await createServerApiFactory();
    const response = await factory.getModelsClient().getModels({
      sort_by: 'name',
      sort_order: 'asc',
      skip: 0,
      limit: 100,
    });
    initialModels = response.data;
  } catch {
    // Fall back to the client fetch.
  }

  return <NewMetricForm type={type} initialModels={initialModels} />;
}
