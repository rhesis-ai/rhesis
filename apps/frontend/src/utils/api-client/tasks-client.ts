import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Task, TaskCreate, TaskUpdate, TasksQueryParams } from './interfaces/task';

export class TasksClient extends BaseApiClient {
  constructor(sessionToken: string) {
    super(sessionToken);
  }

  async getTasks(params: TasksQueryParams = {}): Promise<Task[]> {
    const queryParams = new URLSearchParams();
    
    if (params.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.$filter) queryParams.append('$filter', params.$filter);

    const response = await this.fetch<Task[]>(`${API_ENDPOINTS.tasks}?${queryParams.toString()}`);
    return response;
  }

  async getTask(taskId: string): Promise<Task> {
    const response = await this.fetch<Task>(`${API_ENDPOINTS.tasks}/${taskId}`);
    return response;
  }

  async createTask(taskData: TaskCreate): Promise<Task> {
    const response = await this.fetch<Task>(API_ENDPOINTS.tasks, {
      method: 'POST',
      body: JSON.stringify(taskData)
    });
    return response;
  }

  async updateTask(taskId: string, taskData: TaskUpdate): Promise<Task> {
    const response = await this.fetch<Task>(`${API_ENDPOINTS.tasks}/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(taskData)
    });
    return response;
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.fetch<void>(`${API_ENDPOINTS.tasks}/${taskId}`, {
      method: 'DELETE'
    });
  }

  async getTasksByEntity(entityType: string, entityId: string, params: TasksQueryParams = {}): Promise<Task[]> {
    const queryParams = new URLSearchParams();
    
    if (params.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);

    const response = await this.fetch<Task[]>(`${API_ENDPOINTS.tasks}/${entityType}/${entityId}?${queryParams.toString()}`);
    return response;
  }
}
