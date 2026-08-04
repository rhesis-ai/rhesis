import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  InsightsBatchRequest,
  InsightsBatchResponse,
} from './interfaces/insights';

export class InsightsClient extends BaseApiClient {
  async getInsightsBatch(
    request: InsightsBatchRequest
  ): Promise<InsightsBatchResponse> {
    return this.fetch<InsightsBatchResponse>(
      `${API_ENDPOINTS.insights}/batch`,
      {
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
      }
    );
  }
}
