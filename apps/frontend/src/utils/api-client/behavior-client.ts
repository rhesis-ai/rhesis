import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Behavior, BehaviorCreate, BehaviorUpdate, BehaviorsQueryParams } from './interfaces/behavior';
import { UUID } from 'crypto';

export class BehaviorClient extends BaseApiClient {
  async getBehaviors(params: BehaviorsQueryParams = {}): Promise<Behavior[]> {
    const { skip = 0, limit = 100, sort_by = 'created_at', sort_order = 'desc', $filter } = params;
    
    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    if ($filter) {
      queryParams.append('$filter', $filter);
    }
    
    const url = `${API_ENDPOINTS.behaviors}?${queryParams.toString()}`;
    
    return this.fetch<Behavior[]>(url, {
      cache: 'no-store'
    });
  }

  async getBehavior(id: UUID): Promise<Behavior> {
    return this.fetch<Behavior>(`${API_ENDPOINTS.behaviors}/${id}`);
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
} 