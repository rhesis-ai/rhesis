import type { WithPermittedActions } from '@/types/affordances';
import type { UserReference } from './tests';
import type { PaginationParams } from './pagination';

export type ReportStatus = 'draft' | 'published';
export type ReportRecommendation = 'ready' | 'ready_with_risks' | 'not_ready';
/** latest: newest run per test. all: every result (averages). worst: any failure fails. */
export type ReportResultRule = 'latest' | 'all' | 'worst';
export type ReportCoverage =
  | 'tested'
  | 'errored_only'
  | 'not_in_runs'
  | 'no_tests';

export interface Report extends WithPermittedActions {
  id: string;
  title: string;
  summary?: string | null;
  recommendation?: ReportRecommendation | null;
  result_rule: ReportResultRule;
  /** Off for a plain report across runs: no ship recommendation. */
  is_release: boolean;
  /** While a draft, runs on the endpoint with this tag join the report. */
  run_tag?: string | null;
  /** The published report this one is compared with. */
  baseline_report_id?: string | null;
  endpoint_id: string;
  status: ReportStatus;
  user_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  published_at?: string | null;
  published_by_id?: string | null;
  snapshot_hash?: string | null;
  user?: UserReference | null;
  published_by?: UserReference | null;
  endpoint?: { id: string; name: string } | null;
}

export interface ReportRequirementRow {
  id: string;
  name: string;
  description?: string | null;
  parent_id?: string | null;
  level: number;
  coverage: ReportCoverage;
  tests: number;
  passed: number;
  failed: number;
  errored: number;
  pass_rate?: number | null;
  /** Tests whose verdict differed between runs (all and worst rules). */
  inconsistent: number;
  /** Judged on fewer than 10 results. */
  low_sample?: boolean;
  /** Change against the previous published report, in percentage points. */
  pass_rate_delta?: number | null;
}

export interface ReportRunRow {
  id: string;
  name?: string | null;
  created_at?: string | null;
  user_id?: string | null;
  results: number;
  /** The run's own pass rate over all its results, whatever the counting rule. */
  pass_rate?: number | null;
  status?: string | null;
  test_set?: string | null;
  version_info?: Record<string, unknown> | null;
  /** The experiment whose parameters the run used. */
  experiment?: { id?: string | null; name: string; version: string } | null;
}

export interface ReportTotals {
  results: number;
  passed: number;
  failed: number;
  inconclusive: number;
  errored: number;
  pass_rate?: number | null;
  requirements_tested: number;
  requirements_total: number;
  inconsistent: number;
}

export interface ReportWarning {
  kind: string;
  text: string;
}

export interface ReportComparison {
  baseline: {
    id: string;
    title: string;
    published_at?: string | null;
    result_rule: ReportResultRule;
  };
  pass_rate_delta?: number | null;
  newly_failing: number;
  fixed: number;
  newly_failing_requirements: string[];
}

export type ReportMetricKind = 'llm' | 'jev' | 'code';

export interface ReportMetricResult {
  name: string;
  /** llm: an LLM judge; jev: a classifier with a Jev model; code: a code check. */
  kind: ReportMetricKind;
  passed: number;
  failed: number;
  pass_rate?: number | null;
}

export interface ReportRequirementMetrics {
  requirement_id: string;
  name: string;
  level: number;
  metrics: ReportMetricResult[];
}

export interface ReportMetrics {
  result_rule: ReportResultRule;
  totals: ReportTotals;
  requirements: ReportRequirementRow[];
  runs: ReportRunRow[];
  versions_differ: boolean;
  warnings?: ReportWarning[];
  comparison?: ReportComparison | null;
  metric_results?: ReportRequirementMetrics[];
}

export interface ReportDetail extends Report {
  test_run_ids: string[];
  /** Runs that joined through the run tag, not picked by hand. */
  tagged_run_ids: string[];
  requirement_ids: string[];
  metrics?: ReportMetrics | null;
  /** Output of the extra sections the org is entitled to, keyed by section. */
  sections: Record<string, unknown>;
}

export interface ReportCreate {
  title: string;
  endpoint_id: string;
  summary?: string | null;
  recommendation?: ReportRecommendation | null;
  result_rule?: ReportResultRule;
  is_release?: boolean;
  run_tag?: string | null;
  baseline_report_id?: string | null;
  test_run_ids: string[];
  requirement_ids: string[];
}

export type ReportUpdate = Partial<
  Omit<ReportCreate, 'endpoint_id'> & { summary: string | null }
>;

export interface ReportSummaryDraft {
  summary: string;
  /** Null outside a release report. */
  recommendation: ReportRecommendation | null;
}

export type ReportsQueryParams = Partial<PaginationParams>;
