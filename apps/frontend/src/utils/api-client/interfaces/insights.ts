/** Registry entities exposed by Insights endpoints — see backend `services/insights/registry.py`. */
export type InsightsEntity = 'test_result' | 'metric' | 'test_run' | 'test';

/** One named sub-query in a POST /insights/query request. */
export interface InsightsQuery {
  entity: InsightsEntity;
  group_by?: string[];
  measures?: string[];
  filters?: Record<string, string[]>;
  months?: number;
  start_date?: string;
  end_date?: string;
}

/** Body of POST /insights/query: label -> query (no wrapping `queries` key). */
export type InsightsQueryRequest = Record<string, InsightsQuery>;

/** One aggregated row: the requested `group_by` dimension values plus the requested measures. */
export type InsightsRow = Record<string, string | number>;

export interface InsightsResponse {
  entity: string;
  dimensions: string[];
  measures: string[];
  rows: InsightsRow[];
}

/** Response of POST /insights/query: label -> envelope (no wrapping `results` key). */
export type InsightsQueryResponse = Record<string, InsightsResponse>;

export type InsightsOutcome = 'pass' | 'fail' | 'all';

export interface InsightsIdsParams {
  entity: InsightsEntity;
  outcome?: InsightsOutcome;
  months?: number;
  start_date?: string;
  end_date?: string;
  test_run_ids?: string[];
  behavior_ids?: string[];
  category_ids?: string[];
  topic_ids?: string[];
  status_ids?: string[];
  test_ids?: string[];
  test_type_ids?: string[];
  user_ids?: string[];
  assignee_ids?: string[];
  owner_ids?: string[];
  prompt_ids?: string[];
  test_set_ids?: string[];
  tags?: string[];
  metric_names?: string[];
  endpoint_ids?: string[];
}

export interface InsightsIdsResponse {
  entity: string;
  ids: string[];
}
