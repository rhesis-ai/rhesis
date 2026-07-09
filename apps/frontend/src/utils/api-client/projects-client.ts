import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Project,
  ProjectCreate,
  ProjectMember,
  ProjectMemberCreate,
  ProjectUpdate,
  ProjectsQueryParams,
} from './interfaces/project';
import { PaginatedResponse } from './interfaces/pagination';

export class ProjectsClient extends BaseApiClient {
  async getProjects(
    params: ProjectsQueryParams = {}
  ): Promise<PaginatedResponse<Project>> {
    const { skip = 0, limit = 10, sort_by, sort_order, $filter } = params;
    return this.fetchPaginated<Project>(API_ENDPOINTS.projects, {
      skip,
      limit,
      sort_by,
      sort_order,
      $filter,
    });
  }

  async getAllProjects(
    params?: Omit<ProjectsQueryParams, 'skip' | 'limit'>
  ): Promise<Project[]> {
    const pageSize = 100;
    const allData: Project[] = [];
    let skip = 0;
    let totalCount = Infinity;

    while (skip < totalCount) {
      const response = await this.getProjects({
        ...params,
        skip,
        limit: pageSize,
      });
      if (response.data.length === 0) break;
      allData.push(...response.data);
      totalCount = response.pagination.totalCount;
      skip += pageSize;
    }

    return allData;
  }

  async getProject(id: string): Promise<Project> {
    return this.fetch<Project>(`${API_ENDPOINTS.projects}/${id}`);
  }

  async createProject(project: ProjectCreate): Promise<Project> {
    try {
      return await this.fetch<Project>(`${API_ENDPOINTS.projects}/`, {
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

  /** Projects the current user is a member of (used by the project switcher). */
  async getMyProjects(): Promise<Project[]> {
    return this.fetch<Project[]>(`${API_ENDPOINTS.projects}/mine`);
  }

  async getProjectMembers(projectId: string): Promise<ProjectMember[]> {
    return this.fetch<ProjectMember[]>(
      `${API_ENDPOINTS.projects}/${projectId}/members`
    );
  }

  async addProjectMember(
    projectId: string,
    body: ProjectMemberCreate
  ): Promise<ProjectMember> {
    return this.fetch<ProjectMember>(
      `${API_ENDPOINTS.projects}/${projectId}/members`,
      { method: 'POST', body: JSON.stringify(body) }
    );
  }

  async removeProjectMember(projectId: string, userId: string): Promise<void> {
    return this.fetch<void>(
      `${API_ENDPOINTS.projects}/${projectId}/members/${userId}`,
      { method: 'DELETE' }
    );
  }
}
