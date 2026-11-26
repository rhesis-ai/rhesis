import type { WithPermittedActions } from '@/types/affordances';
import type {
  PausedReason,
  ScheduleNotify,
  ScheduleScope,
  ScheduleStatus,
  ScheduleTrigger,
} from '@/constants/test-run-schedules';

/** When and how a schedule runs. Exactly one of `cron` and `run_at` is set. */
export interface ScheduleSpec {
  name: string;
  cron: string | null;
  run_at: string | null;
  timezone: string;
  ends_at?: string | null;
  max_runs?: number | null;
  notify?: ScheduleNotify;
}

/** What each run uses; the same body the run drawer sends to execute a test set. */
export interface ScheduleRunSettings {
  execution_options?: Record<string, unknown>;
  metrics?: { id: string; name: string; scope?: string[] }[];
  execution_model_id?: string | null;
  evaluation_model_id?: string | null;
  tests_tagged?: string[];
}

export interface TestRunScheduleCreate {
  test_set_id?: string;
  test_set_ids?: string[];
  endpoint_id: string;
  schedule: ScheduleSpec;
  run_settings?: ScheduleRunSettings;
}

export interface TestRunScheduleUpdate extends Partial<ScheduleSpec> {
  endpoint_id?: string;
  run_settings?: ScheduleRunSettings;
}

export interface OccurrenceEdit extends TestRunScheduleUpdate {
  /** The new time of this one run. */
  move_to?: string;
}

export interface NamedRef {
  id: string;
  name: string | null;
}

export interface ScheduleRunSummary {
  id: string;
  name: string | null;
  status: string | null;
  pass_rate: number | null;
  started_at: string | null;
  duration_s: number | null;
  total_cost_usd: number | null;
  trigger: ScheduleTrigger | null;
  scheduled_for: string | null;
}

export interface TestRunSchedule extends WithPermittedActions {
  id: string;
  name: string;
  status: ScheduleStatus | null;
  overdue: boolean;
  /** Plain words, e.g. "Every weekday at 09:00". Never a cron expression. */
  repeats: string;
  cron: string | null;
  run_at: string | null;
  timezone: string;
  next_run_at: string | null;
  ends_at: string | null;
  max_runs: number | null;
  notify: ScheduleNotify;
  paused_reason: PausedReason | null;
  last_skip: { at: string; reason: string } | null;
  test_set: NamedRef | null;
  endpoint: (NamedRef & { connection_type: string | null }) | null;
  owner: NamedRef | null;
  user_id: string | null;
  created_at: string | null;
  last_run: ScheduleRunSummary | null;
}

export interface ScheduleUsage {
  run_count: number;
  first_run_at: string | null;
  total_cost_usd: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  avg_cost_usd: number | null;
  /** Hidden until a few runs exist. */
  expected_month_usd: number | null;
}

export interface TestRunScheduleDetail extends TestRunSchedule {
  upcoming: string[];
  recent_runs: ScheduleRunSummary[];
  usage: ScheduleUsage;
  run_settings: {
    metrics_source: string | null;
    metrics: { id: string; name: string }[];
    execution_model_id: string | null;
    evaluation_model_id: string | null;
    execution_mode: string | null;
    tests_tagged: string[];
  };
}

export interface ScheduleOccurrence {
  schedule_id: string;
  name: string;
  /** The time the schedule originally put this run; the key for edits. */
  occurrence: string;
  /** When it runs, after any change to this one run. */
  at: string;
  changed: boolean;
}

export interface ScheduleOccurrences {
  items: ScheduleOccurrence[];
  /** Schedules that run every hour; shown in a strip, not on every day. */
  hourly: NamedRef[];
}

export interface SchedulePreview {
  repeats: string;
  next: string[];
}

export interface ScheduleListParams {
  test_set_id?: string;
  status?: ScheduleStatus[];
}

export type { ScheduleScope };
