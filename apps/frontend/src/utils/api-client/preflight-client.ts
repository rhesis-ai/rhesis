import { BaseApiClient } from './base-client';

export interface PreflightMetricRef {
  id: string;
  name: string;
  scope?: string[];
}

export interface PreflightCheckRequest {
  test_set_ids: string[];
  endpoint_id: string;
  correlation_id?: string;
  scoring_target?: string;
  metric_mode?: string;
  selected_metrics?: PreflightMetricRef[];
  execution_model_id?: string;
  evaluation_model_id?: string;
  mode?: 'async' | 'sync';
}

export interface PreflightCheckInfo {
  check_id: string;
  label: string;
  applicable: boolean;
  test_set_id?: string;
  test_set_name?: string;
  composite_key?: string;
}

export interface PreflightCheckResponse {
  correlation_id: string;
  checks: PreflightCheckInfo[];
}

export class PreflightClient extends BaseApiClient {
  async runPreflightChecks(
    params: PreflightCheckRequest
  ): Promise<PreflightCheckResponse> {
    return this.fetch<PreflightCheckResponse>('/preflight-checks', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }
}
