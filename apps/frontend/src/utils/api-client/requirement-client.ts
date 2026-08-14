import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Requirement,
  RequirementCreate,
  RequirementUpdate,
  RequirementsQueryParams,
  RequirementWithMetrics,
} from './interfaces/requirement';
import { PaginatedResponse } from './interfaces/pagination';
import { UUID } from 'crypto';
import { MetricDetail } from './interfaces/metric';

export class RequirementClient extends BaseApiClient {
  /**
   * Fetch a single page of requirements along with the total matching count
   * (via the X-Total-Count header). Use this for server-side pagination
   * instead of getAllRequirements()/getRequirements(), which fetch everything.
   */
  async getRequirementsPage(
    params: RequirementsQueryParams = {}
  ): Promise<PaginatedResponse<RequirementWithMetrics>> {
    const {
      skip = 0,
      limit = 25,
      sort_by = 'created_at',
      sort_order = 'desc',
      $filter,
    } = params;

    return this.fetchPaginated<RequirementWithMetrics>(
      API_ENDPOINTS.requirements,
      {
        skip,
        limit,
        sort_by,
        sort_order,
        $filter,
      },
      { cache: 'no-store' }
    );
  }

  async getRequirements(
    params: RequirementsQueryParams = {}
  ): Promise<RequirementWithMetrics[]> {
    const {
      skip = 0,
      limit = 100,
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
    // Note: The backend now always returns requirements with metrics and their relationships
    // No need for conditional include parameter since get_items_detail always loads relationships

    const url = `${API_ENDPOINTS.requirements}/?${queryParams.toString()}`;

    return this.fetch<RequirementWithMetrics[]>(url, {
      cache: 'no-store',
    });
  }

  /** Paginate through all requirements (page size 100) for lookups / filter drawers. */
  async getAllRequirements(
    params: Omit<RequirementsQueryParams, 'skip' | 'limit'> = {}
  ): Promise<RequirementWithMetrics[]> {
    const pageSize = 100;
    const allData: RequirementWithMetrics[] = [];
    let skip = 0;

    while (true) {
      const page = await this.getRequirements({
        ...params,
        skip,
        limit: pageSize,
      });
      if (page.length === 0) break;
      allData.push(...page);
      if (page.length < pageSize) break;
      skip += pageSize;
    }

    return allData;
  }

  async getRequirement(id: UUID): Promise<Requirement> {
    return this.fetch<Requirement>(`${API_ENDPOINTS.requirements}/${id}`);
  }

  async getRequirementWithMetrics(id: UUID): Promise<RequirementWithMetrics> {
    const queryParams = new URLSearchParams();
    queryParams.append('include', 'metrics');

    const url = `${API_ENDPOINTS.requirements}/${id}?${queryParams.toString()}`;

    return this.fetch<RequirementWithMetrics>(url, {
      cache: 'no-store',
    });
  }

  async getRequirementsWithMetrics(
    params: Omit<RequirementsQueryParams, 'include'> = {}
  ): Promise<RequirementWithMetrics[]> {
    try {
      // Since getRequirements now always returns RequirementWithMetrics, we can just call it directly
      const result = await this.getRequirements(params);
      return result;
    } catch (error) {
      throw error;
    }
  }

  async createRequirement(
    requirement: RequirementCreate
  ): Promise<Requirement> {
    return this.fetch<Requirement>(`${API_ENDPOINTS.requirements}/`, {
      method: 'POST',
      body: JSON.stringify(requirement),
    });
  }

  async updateRequirement(
    id: UUID,
    requirement: RequirementUpdate
  ): Promise<Requirement> {
    return this.fetch<Requirement>(`${API_ENDPOINTS.requirements}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(requirement),
    });
  }

  async deleteRequirement(id: UUID): Promise<Requirement> {
    return this.fetch<Requirement>(`${API_ENDPOINTS.requirements}/${id}`, {
      method: 'DELETE',
    });
  }

  async getRequirementMetrics(
    requirementId: UUID,
    params: { skip?: number; limit?: number } = {}
  ): Promise<MetricDetail[]> {
    const { skip = 0, limit = 100 } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());

    const url = `${API_ENDPOINTS.requirements}/${requirementId}/metrics/?${queryParams.toString()}`;

    return this.fetch<MetricDetail[]>(url, {
      cache: 'no-store',
    });
  }
}
