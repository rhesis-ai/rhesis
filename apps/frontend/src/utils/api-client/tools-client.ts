import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
  ToolsQueryParams,
} from './interfaces/tool';
import { PaginatedResponse } from './interfaces/pagination';

export class ToolsClient extends BaseApiClient {
  async getTools(
    params: ToolsQueryParams = {}
  ): Promise<PaginatedResponse<Tool>> {
    const { skip = 0, limit = 10, sort_by, sort_order, $filter } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    if (sort_by) queryParams.append('sort_by', sort_by);
    if (sort_order) queryParams.append('sort_order', sort_order);
    if ($filter) queryParams.append('$filter', $filter);

    const url = `${API_ENDPOINTS.tools}?${queryParams.toString()}`;

    return this.fetch<PaginatedResponse<Tool>>(url, {
      cache: 'no-store',
    });
  }

  async getTool(id: string): Promise<Tool> {
    return this.fetch<Tool>(`${API_ENDPOINTS.tools}/${id}`);
  }

  async createTool(tool: ToolCreate): Promise<Tool> {
    try {
      return await this.fetch<Tool>(API_ENDPOINTS.tools, {
        method: 'POST',
        body: JSON.stringify(tool),
      });
    } catch (error) {
      throw error;
    }
  }

  async updateTool(id: string, tool: ToolUpdate): Promise<Tool> {
    return this.fetch<Tool>(`${API_ENDPOINTS.tools}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(tool),
    });
  }

  async deleteTool(id: string): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.tools}/${id}`, {
      method: 'DELETE',
    });
  }
}
