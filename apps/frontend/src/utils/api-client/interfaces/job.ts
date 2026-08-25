/**
 * A background job, as `GET /jobs/` returns it.
 *
 * Mirrors `apps/backend/src/rhesis/backend/app/schemas/job.py`. `is_terminal`
 * and `cancellable` are computed by the backend rather than derived here on
 * purpose: keeping a second copy of "which statuses are final" in the frontend
 * would silently rot the next time one is added.
 */

/** Values of the backend `JobStatus` enum. */
export type JobStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface Job {
  id: string;
  nano_id?: string;
  organization_id?: string;
  project_id?: string;
  user_id?: string;

  celery_task_id?: string;
  /** W3C trace id, for correlating with traces and log lines. */
  trace_id?: string;

  /** e.g. `generate_and_save_test_set`. */
  job_type: string;
  /** Human label, e.g. "Generate and Save Test Set". */
  name?: string;
  status: JobStatus | string;

  /** What the job is about, so the UI can link back to it. */
  entity_type?: string;
  entity_id?: string;

  progress_current?: number;
  progress_total?: number;

  queued_at?: string;
  started_at?: string;
  finished_at?: string;

  error_message?: string;
  error_type?: string;
  attempt: number;

  job_metadata?: Record<string, unknown>;

  /** Display name of the user who started this job. */
  user_display_name?: string;

  created_at: string;
  updated_at: string;

  /** Server-computed: the job has stopped for good. */
  is_terminal: boolean;
  /** Server-computed: asking this job to stop could still do something. */
  cancellable: boolean;
}

/** User-facing severities. Deliberately not Python's logging levels. */
export type ActivityLevel = 'info' | 'warning' | 'error';

export interface ActivityLogEntry {
  id: string;
  job_id?: string;
  entity_type?: string;
  entity_id?: string;
  source?: string;
  /** Monotonic per job; the cursor pages on this, not on timestamps. */
  sequence?: number;
  level: ActivityLevel | string;
  message: string;
  context?: Record<string, unknown>;
  created_at: string;
}

export interface JobActivity {
  entries: ActivityLogEntry[];
  /**
   * Cursor to pass as `after_sequence` next poll. Returned by the server rather
   * than read off the last entry so an empty page still advances correctly.
   */
  next_after_sequence?: number;
}

export interface JobsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
}
