import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Status, StatusesQueryParams } from './interfaces/status';

export class StatusClient extends BaseApiClient {
  async getStatuses(params: StatusesQueryParams = {}): Promise<Status[]> {
    const {
      skip = 0,
      limit = 100,
      entity_type,
      sort_by,
      sort_order,
      $filter,
    } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    if (entity_type) {
      queryParams.append('entity_type', entity_type);
    }
    if (sort_by) {
      queryParams.append('sort_by', sort_by);
    }
    if (sort_order) {
      queryParams.append('sort_order', sort_order);
    }
    if ($filter) {
      queryParams.append('$filter', $filter);
    }

    const url = `${API_ENDPOINTS.statuses}?${queryParams.toString()}`;

    return this.fetch<Status[]>(url, {
      cache: 'no-store',
    });
  }

  async getStatus(id: string): Promise<Status> {
    return this.fetch<Status>(`${API_ENDPOINTS.statuses}/${id}`);
  }
}
