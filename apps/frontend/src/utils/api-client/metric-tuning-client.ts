import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  MetricTuningCase,
  MetricTuningCaseCreate,
  MetricTuningCaseDeleteResponse,
  MetricTuningCaseUpdate,
} from './interfaces/metric-tuning';
import { UUID } from 'crypto';

/**
 * Client for the experimental metric tuning endpoints.
 *
 * Kept separate from `MetricsClient` so the feature can be removed by deleting
 * this file, its interfaces file, and one factory getter.
 */
export class MetricTuningClient extends BaseApiClient {
  private basePath(metricId: UUID | string): string {
    return `${API_ENDPOINTS.metrics}/${metricId}/tuning/cases`;
  }

  /** Cases for a metric. Empty when it has no tuning test set yet. */
  async getTuningCases(metricId: UUID | string): Promise<MetricTuningCase[]> {
    return this.fetch<MetricTuningCase[]>(this.basePath(metricId), {
      cache: 'no-store',
    });
  }

  /** Adds a case, creating the metric's tuning test set on the first call. */
  async createTuningCase(
    metricId: UUID | string,
    data: MetricTuningCaseCreate
  ): Promise<MetricTuningCase> {
    return this.fetch<MetricTuningCase>(this.basePath(metricId), {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateTuningCase(
    metricId: UUID | string,
    caseId: UUID | string,
    data: MetricTuningCaseUpdate
  ): Promise<MetricTuningCase> {
    return this.fetch<MetricTuningCase>(
      `${this.basePath(metricId)}/${caseId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      }
    );
  }

  async deleteTuningCase(
    metricId: UUID | string,
    caseId: UUID | string
  ): Promise<MetricTuningCaseDeleteResponse> {
    return this.fetch<MetricTuningCaseDeleteResponse>(
      `${this.basePath(metricId)}/${caseId}`,
      { method: 'DELETE' }
    );
  }
}
