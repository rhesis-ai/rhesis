import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Requirement,
  RequirementCreate,
  RequirementUpdate,
  RequirementsQueryParams,
  RequirementWithMetrics,
  RequirementExample,
  RequirementReview,
  RequirementOption,
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

  async getRequirements<T = RequirementWithMetrics>(
    params: RequirementsQueryParams = {}
  ): Promise<T[]> {
    const {
      skip = 0,
      limit = 100,
      sort_by = 'created_at',
      sort_order = 'desc',
      $filter,
      $select,
      include: _include,
    } = params;

    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    if ($filter) {
      queryParams.append('$filter', $filter);
    }
    if ($select) {
      queryParams.append('$select', $select);
    }

    const url = `${API_ENDPOINTS.requirements}/?${queryParams.toString()}`;

    return this.fetch<T[]>(url, {
      cache: 'no-store',
    });
  }

  /**
   * Paginate through all requirements (page size 100) for lookups / filter drawers.
   * Pass `$select` to trim the response: the default shape inlines every
   * requirement's full metric list, which callers rendering a name list don't need.
   */
  async getAllRequirements<T = RequirementWithMetrics>(
    params: Omit<RequirementsQueryParams, 'skip' | 'limit'> = {}
  ): Promise<T[]> {
    return this.fetchAllPages((skip, limit) =>
      this.getRequirements<T>({ ...params, skip, limit })
    );
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

  /** Direct children of a requirement: id, name and description. */
  async getChildRequirements(
    id: UUID
  ): Promise<(RequirementOption & { description?: string | null })[]> {
    return this.getAllRequirements<
      RequirementOption & { description?: string | null }
    >({
      $filter: `parent_id eq ${id}`,
      $select: 'id,name,description',
      sort_by: 'name',
      sort_order: 'asc',
    });
  }

  /** Links a knowledge source. Linking again replaces the note. */
  async linkSource(
    id: UUID,
    sourceId: UUID | string,
    note: string | null = null
  ): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.requirements}/${id}/sources/${sourceId}`,
      {
        method: 'POST',
        body: JSON.stringify({ note }),
      }
    );
  }

  async unlinkSource(id: UUID, sourceId: UUID | string): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.requirements}/${id}/sources/${sourceId}`,
      { method: 'DELETE' }
    );
  }

  /** Annotations that name this requirement, with the conversation they judged. */
  async getExamples(id: UUID): Promise<RequirementExample[]> {
    return this.fetch<RequirementExample[]>(
      `${API_ENDPOINTS.requirements}/${id}/examples`,
      { cache: 'no-store' }
    );
  }

  /**
   * Asks the generation model to review the name and description. One LLM
   * call, so only ever from an explicit action. The result is also stored.
   */
  async reviewRequirement(id: UUID): Promise<RequirementReview> {
    return this.fetch<RequirementReview>(
      `${API_ENDPOINTS.requirements}/${id}/review`,
      { method: 'POST' }
    );
  }
}
