import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Report } from '@/utils/api-client/interfaces/report';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

const REPORTS_FILTERS = {
  search: { kind: 'search', columns: ['title', 'endpoint/name', 'user/name'] },
  status: { kind: 'enum', column: 'status' },
} as const;

export const reportsList = defineList<Report, typeof REPORTS_FILTERS>({
  title: 'Reports',
  resource: 'reports',
  capability: Capability.Report.READ,
  defaultPageSize: 25,
  filters: REPORTS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getReportsClient().getReportsPage(params),
  delete: {
    one: (factory: ApiClientFactory, id: string) =>
      factory.getReportsClient().deleteReport(id),
    capability: Capability.Report.DELETE,
    // A published report carries no report:delete, so its row can't be deleted.
    capabilityMode: 'row',
    labelSingular: 'report',
    labelPlural: 'reports',
    notSelectableReason: 'Published reports are kept and cannot be deleted',
  },
});
