import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import type {
  InsightsIdsParams,
  InsightsIdsResponse,
  InsightsQueryRequest,
  InsightsQueryResponse,
} from './interfaces/insights';

function appendListParam(
  searchParams: URLSearchParams,
  key: string,
  values: string[] | undefined
): void {
  if (!values) return;
  for (const value of values) {
    searchParams.append(key, value);
  }
}

export class InsightsClient extends BaseApiClient {
  async getInsightsQuery(
    request: InsightsQueryRequest
  ): Promise<InsightsQueryResponse> {
    return this.fetch<InsightsQueryResponse>(
      `${API_ENDPOINTS.insights}/query`,
      {
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
      }
    );
  }

  async getInsightsIds(
    params: InsightsIdsParams
  ): Promise<InsightsIdsResponse> {
    const searchParams = new URLSearchParams();
    searchParams.set('entity', params.entity);
    if (params.outcome) {
      searchParams.set('outcome', params.outcome);
    }
    if (params.months != null) {
      searchParams.set('months', String(params.months));
    }
    if (params.start_date) {
      searchParams.set('start_date', params.start_date);
    }
    if (params.end_date) {
      searchParams.set('end_date', params.end_date);
    }
    appendListParam(searchParams, 'test_run_ids', params.test_run_ids);
    appendListParam(searchParams, 'requirement_ids', params.requirement_ids);
    appendListParam(searchParams, 'category_ids', params.category_ids);
    appendListParam(searchParams, 'topic_ids', params.topic_ids);
    appendListParam(searchParams, 'status_ids', params.status_ids);
    appendListParam(searchParams, 'test_ids', params.test_ids);
    appendListParam(searchParams, 'test_type_ids', params.test_type_ids);
    appendListParam(searchParams, 'user_ids', params.user_ids);
    appendListParam(searchParams, 'assignee_ids', params.assignee_ids);
    appendListParam(searchParams, 'owner_ids', params.owner_ids);
    appendListParam(searchParams, 'prompt_ids', params.prompt_ids);
    appendListParam(searchParams, 'test_set_ids', params.test_set_ids);
    appendListParam(searchParams, 'tags', params.tags);
    appendListParam(searchParams, 'metric_names', params.metric_names);
    appendListParam(searchParams, 'endpoint_ids', params.endpoint_ids);

    return this.fetch<InsightsIdsResponse>(
      `${API_ENDPOINTS.insights}/ids?${searchParams.toString()}`,
      { cache: 'no-store' }
    );
  }
}
