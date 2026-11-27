import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  MetricCreate,
  MetricUpdate,
  MetricDetail,
  MetricQueryParams,
  MetricSaved,
  MetricTargetChoice,
  MetricTargetOptions,
  MetricTargetPreview,
  MetricTargetPreviewRequest,
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

    // The metrics endpoint now includes all relationships (requirements, metric_type, backend_type)
    // using get_items_detail with joinedloads
    return this.fetchPaginated<MetricDetail>(
      API_ENDPOINTS.metrics,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  async getAllMetrics(
    params?: Omit<MetricQueryParams, 'skip' | 'limit'>
  ): Promise<MetricDetail[]> {
    return this.fetchAllPages((skip, limit) =>
      this.getMetrics({ ...params, skip, limit })
    );
  }

  /**
   * The target registry (what a metric can judge, in display order), and the
   * operators and special fields a target condition takes.
   */
  async getMetricTargetOptions(): Promise<MetricTargetOptions> {
    const options = await this.fetch<Partial<MetricTargetOptions>>(
      `${API_ENDPOINTS.metrics}/targets`
    );
    return {
      targets: options.targets ?? [],
      operators: options.operators ?? [],
      special_fields: options.special_fields ?? [],
      readers: options.readers ?? [],
      event_prefix: options.event_prefix ?? null,
    };
  }

  /** The target registry alone: what a metric can judge, in display order. */
  async getMetricTargets(): Promise<MetricTargetChoice[]> {
    return (await this.getMetricTargetOptions()).targets;
  }

  /** What a target picks in a project's latest traces, before any metric runs. */
  async previewMetricTarget(
    request: MetricTargetPreviewRequest,
    signal?: AbortSignal
  ): Promise<MetricTargetPreview> {
    return this.fetch<MetricTargetPreview>(
      `${API_ENDPOINTS.metrics}/targets/preview`,
      { method: 'POST', body: JSON.stringify(request), signal }
    );
  }

  async getMetric(id: UUID): Promise<MetricDetail> {
    return this.fetch<MetricDetail>(`${API_ENDPOINTS.metrics}/${id}`);
  }

  async createMetric(metric: MetricCreate): Promise<MetricSaved> {
    return this.fetch<MetricSaved>(`${API_ENDPOINTS.metrics}/`, {
      method: 'POST',
      body: JSON.stringify(metric),
    });
  }

  async updateMetric(id: UUID, metric: MetricUpdate): Promise<MetricSaved> {
    return this.fetch<MetricSaved>(`${API_ENDPOINTS.metrics}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(metric),
    });
  }

  async deleteMetric(id: UUID): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.metrics}/${id}`, {
      method: 'DELETE',
    });
  }

  async addRequirementToMetric(
    metricId: UUID,
    requirementId: UUID
  ): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.metrics}/${metricId}${API_ENDPOINTS.requirements}/${requirementId}`,
      {
        method: 'POST',
      }
    );
  }

  async removeRequirementFromMetric(
    metricId: UUID,
    requirementId: UUID
  ): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.metrics}/${metricId}${API_ENDPOINTS.requirements}/${requirementId}`,
      {
        method: 'DELETE',
      }
    );
  }

  async getMetricRequirements(
    metricId: UUID,
    params?: PaginationParams
  ): Promise<PaginatedResponse<MetricDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<MetricDetail>(
      `${API_ENDPOINTS.metrics}/${metricId}${API_ENDPOINTS.requirements}`,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }
}
