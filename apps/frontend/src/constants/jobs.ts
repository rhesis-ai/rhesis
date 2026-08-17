import type { JobStatus } from '@/utils/api-client/interfaces/job';

/**
 * Job status presentation.
 *
 * Mirrors the backend `JobStatus` enum. Deliberately does *not* encode which
 * statuses are terminal or cancellable: the backend serves `is_terminal` and
 * `cancellable` on every job so there is one source of truth for that, rather
 * than a second list here that rots the next time a status is added.
 */
export const JOB_STATUS_OPTIONS: { label: string; value: JobStatus }[] = [
  { label: 'Queued', value: 'queued' },
  { label: 'Running', value: 'running' },
  { label: 'Cancelling', value: 'cancelling' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Cancelled', value: 'cancelled' },
];

/** MUI Chip colours per status. */
export const JOB_STATUS_COLOR: Record<
  JobStatus,
  'default' | 'info' | 'warning' | 'success' | 'error'
> = {
  queued: 'default',
  running: 'info',
  cancelling: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
};

export const JOB_STATUS_LABEL: Record<JobStatus, string> =
  JOB_STATUS_OPTIONS.reduce(
    (acc, opt) => ({ ...acc, [opt.value]: opt.label }),
    {} as Record<JobStatus, string>
  );

/**
 * Job types offered in the filter dropdown.
 *
 * Hand-maintained rather than fetched: the set changes only when a developer
 * adds a Celery job, and a dedicated endpoint to enumerate them would be more
 * moving parts than the problem deserves. Values must match
 * `jobs/tracking.py:job_type_for` output, which is the Celery task name minus
 * the `rhesis.backend.jobs.` prefix.
 */
export const JOB_TYPE_OPTIONS: { label: string; value: string }[] = [
  { label: 'Test set generation', value: 'generate_and_save_test_set' },
  {
    label: 'OWASP test set generation',
    value: 'generate_and_save_owasp_test_set',
  },
  { label: 'Test execution', value: 'execute_test_configuration' },
  { label: 'Execution summary', value: 'execution.results.collect_results' },
  { label: 'Document extraction', value: 'file.extract_text' },
  { label: 'Embedding generation', value: 'embedding.generate_embedding' },
  {
    label: 'Test set similarity graph',
    value: 'embedding.compute_graph_test_set',
  },
  { label: 'Source similarity graph', value: 'embedding.compute_graph_source' },
  { label: 'Garak import', value: 'import_garak_probes' },
  { label: 'Garak sync', value: 'sync_garak_test_set' },
  {
    label: 'Endpoint exploration',
    value: 'endpoint.explore.run_exploration_task',
  },
  { label: 'Architect chat', value: 'architect.architect_chat_task' },
];

/** Activity log level to MUI Chip colour. */
export const ACTIVITY_LEVEL_COLOR: Record<
  string,
  'default' | 'warning' | 'error'
> = {
  info: 'default',
  warning: 'warning',
  error: 'error',
};
