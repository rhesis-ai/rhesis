/** Registry entities exposed by `POST /insights/batch` — see backend `services/insights/registry.py`. */
export type InsightsEntity = 'test_result' | 'metric' | 'test_run' | 'test';

/** One named sub-query in an insights batch request. */
export interface InsightsQuery {
  entity: InsightsEntity;
  group_by?: string[];
  measures?: string[];
  filters?: Record<string, string[]>;
  months?: number;
  start_date?: string;
  end_date?: string;
}

export interface InsightsBatchRequest {
  queries: Record<string, InsightsQuery>;
}

/** One aggregated row: the requested `group_by` dimension values plus the requested measures. */
export type InsightsRow = Record<string, string | number>;

export interface InsightsResponse {
  entity: string;
  dimensions: string[];
  measures: string[];
  rows: InsightsRow[];
}

export interface InsightsBatchResponse {
  results: Record<string, InsightsResponse>;
}
