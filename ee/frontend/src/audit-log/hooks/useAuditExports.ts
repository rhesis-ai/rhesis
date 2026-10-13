import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Job } from '@/utils/api-client/interfaces/job';
import { escapeODataValue } from '@/utils/odata-filter';
import { AuditLogClient } from '../api/audit-log-client';
import { auditLogQueryKeys } from '../filters';
import { AUDIT_EXPORT_JOB_TYPE, type AuditExportCreate } from '../types';

export const RECENT_EXPORTS_LIMIT = 10;
/** How often the list refreshes while an export is still running. */
const RUNNING_POLL_MS = 5_000;

/** The `$filter` for one user's export jobs. */
export function exportJobsFilter(userId: string): string {
  // user_id is a UUID column: compared unquoted, like the Jobs list does.
  return `job_type eq '${AUDIT_EXPORT_JOB_TYPE}' and user_id eq ${escapeODataValue(userId)}`;
}

/** The signed-in user's recent exports, from the Jobs API. Polls only while one is unfinished. */
export function useAuditExports() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? '';
  return useQuery({
    queryKey: auditLogQueryKeys.exports(userId),
    queryFn: async (): Promise<Job[]> => {
      const page = await new ApiClientFactory().getJobsClient().getJobs({
        limit: RECENT_EXPORTS_LIMIT,
        sort_by: 'created_at',
        sort_order: 'desc',
        $filter: exportJobsFilter(userId),
      });
      return page.data;
    },
    enabled: !!userId,
    // Fresh on every visit: an export may have finished since.
    staleTime: 0,
    refetchInterval: query =>
      query.state.data?.some(job => !job.is_terminal) ? RUNNING_POLL_MS : false,
  });
}

export function useCreateAuditExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AuditExportCreate) =>
      new AuditLogClient().createExport(body),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: auditLogQueryKeys.allExports(),
      }),
  });
}
