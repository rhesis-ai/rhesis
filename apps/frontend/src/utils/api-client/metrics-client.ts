import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Metric,
  MetricCreate,
  MetricUpdate,
  MetricDetail,
  MetricQueryParams,
} from './interfaces/metric';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import { UUID } from 'crypto';

// Default pagination settings
const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 10,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class MetricsClient extends BaseApiClient {
  async getMetrics(
    params?: MetricQueryParams
  ): Promise<PaginatedResponse<MetricDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    // The metrics endpoint now includes all relationships (behaviors, metric_type, backend_type)
    // using get_items_detail with joinedloads
    return this.fetchPaginated<MetricDetail>(
      API_ENDPOINTS.metrics,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  async getMetric(id: UUID): Promise<MetricDetail> {
    return this.fetch<MetricDetail>(`${API_ENDPOINTS.metrics}/${id}`);
  }

  async createMetric(metric: MetricCreate): Promise<Metric> {
    return this.fetch<Metric>(API_ENDPOINTS.metrics, {
      method: 'POST',
      body: JSON.stringify(metric),
    });
  }

  async updateMetric(id: UUID, metric: MetricUpdate): Promise<Metric> {
    return this.fetch<Metric>(`${API_ENDPOINTS.metrics}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(metric),
    });
  }

  async deleteMetric(id: UUID): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.metrics}/${id}`, {
      method: 'DELETE',
    });
  }

  async addBehaviorToMetric(metricId: UUID, behaviorId: UUID): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.metrics}/${metricId}/behaviors/${behaviorId}`,
      {
        method: 'POST',
      }
    );
  }

  async removeBehaviorFromMetric(
    metricId: UUID,
    behaviorId: UUID
  ): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.metrics}/${metricId}/behaviors/${behaviorId}`,
      {
        method: 'DELETE',
      }
    );
  }

  async getMetricBehaviors(
    metricId: UUID,
    params?: PaginationParams
  ): Promise<PaginatedResponse<MetricDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<MetricDetail>(
      `${API_ENDPOINTS.metrics}/${metricId}/behaviors`,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }
}
