import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, listParams } from '@/utils/list';
import OrganizationSettingsPageClient from './components/OrganizationSettingsPageClient';
import { teamList } from '../team/components/list';

interface OrganizationSettingsPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Server component: when the page opens on the Team tab, fetches the first
 * page of members before rendering so the grid arrives with content already
 * in place -- no client-side spinner on first load. See `prefetchList` for
 * the permission-gating rationale.
 */
export default async function OrganizationSettingsPage({
  searchParams,
}: OrganizationSettingsPageProps) {
  const params = await searchParams;

  // The default tab is Information, so the member list is only needed on first paint for `?tab=team`.
  if (params.tab !== 'team') {
    return <OrganizationSettingsPageClient />;
  }

  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    teamList.capability,
    () =>
      teamList.list(
        factory,
        listParams(teamList, {
          page: 1,
          pageSize: teamList.defaultPageSize,
          sort: teamList.defaultSort,
          filters: emptyFilters(teamList),
        })
      )
  );

  return (
    <OrganizationSettingsPageClient
      initialTeamData={initialData}
      initialTeamTotalCount={initialTotalCount}
    />
  );
}
