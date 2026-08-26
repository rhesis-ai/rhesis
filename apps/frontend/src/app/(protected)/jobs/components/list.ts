import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Job } from '@/utils/api-client/interfaces/job';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';

const JOBS_FILTERS = {
  /** Name and job_type are the two things a user can read off a row. */
  search: { kind: 'search', columns: ['name', 'job_type'] },
  status: { kind: 'enum', column: 'status', caseSensitive: true },
  jobType: { kind: 'enum', column: 'job_type', caseSensitive: true },
  /** UUID compare -- unquoted, unlike string columns. */
  triggeredBy: {
    kind: 'raw',
    toOData: (value: string) =>
      value ? `user_id eq ${escapeODataValue(value)}` : undefined,
  },
  // Inclusive of the whole end day: a user picking today expects today's jobs,
  // and a bare date would compare against midnight and exclude them all.
  createdFrom: {
    kind: 'raw',
    toOData: (value: string) =>
      value ? `created_at ge ${value}T00:00:00Z` : undefined,
  },
  createdTo: {
    kind: 'raw',
    toOData: (value: string) =>
      value ? `created_at le ${value}T23:59:59Z` : undefined,
  },
} as const;

export const jobsList = defineList<Job, typeof JOBS_FILTERS>({
  title: 'Jobs',
  resource: 'jobs',
  capability: Capability.Job.READ,
  defaultPageSize: 25,
  filters: JOBS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getJobsClient().getJobs(params),
});
