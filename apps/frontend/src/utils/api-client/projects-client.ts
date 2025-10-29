import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectsQueryParams,
} from './interfaces/project';
import { PaginatedResponse } from './interfaces/pagination';

export class ProjectsClient extends BaseApiClient {
  async getProjects(
    params: ProjectsQueryParams = {}
  ): Promise<PaginatedResponse<Project>> {
    const { skip = 0, limit = 10, sort_by, sort_order, $filter } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    if (sort_by) queryParams.append('sort_by', sort_by);
    if (sort_order) queryParams.append('sort_order', sort_order);
    if ($filter) queryParams.append('$filter', $filter);

    const url = `${API_ENDPOINTS.projects}?${queryParams.toString()}`;

    return this.fetch<PaginatedResponse<Project>>(url, {
      cache: 'no-store',
    });
  }

  async getProject(id: string): Promise<Project> {
    return this.fetch<Project>(`${API_ENDPOINTS.projects}/${id}`);
  }

  async createProject(project: ProjectCreate): Promise<Project> {
    try {
      return await this.fetch<Project>(API_ENDPOINTS.projects, {
        method: 'POST',
        body: JSON.stringify(project),
      });
    } catch (error) {
      throw error;
    }
  }

  async updateProject(id: string, project: ProjectUpdate): Promise<Project> {
    return this.fetch<Project>(`${API_ENDPOINTS.projects}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(project),
    });
  }

  async deleteProject(id: string): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.projects}/${id}`, {
      method: 'DELETE',
    });
  }
}
