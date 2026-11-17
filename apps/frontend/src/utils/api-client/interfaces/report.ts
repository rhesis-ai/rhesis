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
}

export interface ReportRunRow {
  id: string;
  name?: string | null;
  created_at?: string | null;
  user_id?: string | null;
  results: number;
  version_info?: Record<string, unknown> | null;
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

export interface ReportMetrics {
  result_rule: ReportResultRule;
  totals: ReportTotals;
  requirements: ReportRequirementRow[];
  runs: ReportRunRow[];
  versions_differ: boolean;
}

export interface ReportDetail extends Report {
  test_run_ids: string[];
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
  test_run_ids: string[];
  requirement_ids: string[];
}

export type ReportUpdate = Partial<
  Omit<ReportCreate, 'endpoint_id'> & { summary: string | null }
>;

export interface ReportSummaryDraft {
  summary: string;
  recommendation: ReportRecommendation;
}

export type ReportsQueryParams = Partial<PaginationParams>;
