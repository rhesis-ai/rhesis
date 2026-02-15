import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Behavior,
  BehaviorCreate,
  BehaviorUpdate,
  BehaviorsQueryParams,
  BehaviorWithMetrics,
} from './interfaces/behavior';
import { UUID } from 'crypto';
import { MetricDetail } from './interfaces/metric';

export class BehaviorClient extends BaseApiClient {
  async getBehaviors(
    params: BehaviorsQueryParams = {}
  ): Promise<BehaviorWithMetrics[]> {
    const {
      skip = 0,
      limit = 10,
      sort_by = 'created_at',
      sort_order = 'desc',
      $filter,
      include: _include,
    } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    if ($filter) {
      queryParams.append('$filter', $filter);
    }
    // Note: The backend now always returns behaviors with metrics and their relationships
    // No need for conditional include parameter since get_items_detail always loads relationships

    const url = `${API_ENDPOINTS.behaviors}?${queryParams.toString()}`;

    return this.fetch<BehaviorWithMetrics[]>(url, {
      cache: 'no-store',
    });
  }

  async getBehavior(id: UUID): Promise<Behavior> {
    return this.fetch<Behavior>(`${API_ENDPOINTS.behaviors}/${id}`);
  }

  async getBehaviorWithMetrics(id: UUID): Promise<BehaviorWithMetrics> {
    const queryParams = new URLSearchParams();
    queryParams.append('include', 'metrics');

    const url = `${API_ENDPOINTS.behaviors}/${id}?${queryParams.toString()}`;

    return this.fetch<BehaviorWithMetrics>(url, {
      cache: 'no-store',
    });
  }

  async getBehaviorsWithMetrics(
    params: Omit<BehaviorsQueryParams, 'include'> = {}
  ): Promise<BehaviorWithMetrics[]> {
    try {
      // Since getBehaviors now always returns BehaviorWithMetrics, we can just call it directly
      const result = await this.getBehaviors(params);
      return result;
    } catch (error) {
      throw error;
    }
  }

  async createBehavior(behavior: BehaviorCreate): Promise<Behavior> {
    return this.fetch<Behavior>(API_ENDPOINTS.behaviors, {
      method: 'POST',
      body: JSON.stringify(behavior),
    });
  }

  async updateBehavior(id: UUID, behavior: BehaviorUpdate): Promise<Behavior> {
    return this.fetch<Behavior>(`${API_ENDPOINTS.behaviors}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(behavior),
    });
  }

  async deleteBehavior(id: UUID): Promise<Behavior> {
    return this.fetch<Behavior>(`${API_ENDPOINTS.behaviors}/${id}`, {
      method: 'DELETE',
    });
  }

  async getBehaviorMetrics(
    behaviorId: UUID,
    params: { skip?: number; limit?: number } = {}
  ): Promise<MetricDetail[]> {
    const { skip = 0, limit = 100 } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());

    const url = `${API_ENDPOINTS.behaviors}/${behaviorId}/metrics/?${queryParams.toString()}`;

    return this.fetch<MetricDetail[]>(url, {
      cache: 'no-store',
    });
  }
}
