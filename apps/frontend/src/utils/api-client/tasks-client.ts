import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { 
  Task, 
  TaskCreate, 
  TaskUpdate, 
  TasksQueryParams 
} from './interfaces/task';
import { UUID } from 'crypto';

export class TasksClient extends BaseApiClient {
  async getTasks(params: TasksQueryParams = {}): Promise<Task[]> {
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
    
    const url = `${API_ENDPOINTS.tasks}?${queryParams.toString()}`;
    
    return this.fetch<Task[]>(url, {
      cache: 'no-store'
    });
  }

  async getTask(id: UUID): Promise<Task> {
    return this.fetch<Task>(`${API_ENDPOINTS.tasks}/${id}`);
  }

  async createTask(task: TaskCreate): Promise<Task> {
    return this.fetch<Task>(API_ENDPOINTS.tasks, {
      method: 'POST',
      body: JSON.stringify(task),
    });
  }

  async updateTask(id: UUID, task: TaskUpdate): Promise<Task> {
    return this.fetch<Task>(`${API_ENDPOINTS.tasks}/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(task),
    });
  }

  async deleteTask(id: UUID): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.tasks}/${id}`, {
      method: 'DELETE',
    });
  }

  async getTasksByEntity(entityType: string, entityId: UUID, params: TasksQueryParams = {}): Promise<Task[]> {
    const { skip = 0, limit = 100, sort_by = 'created_at', sort_order = 'desc' } = params;
    
    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    
    const url = `${API_ENDPOINTS.tasks}/${entityType}/${entityId}?${queryParams.toString()}`;
    
    return this.fetch<Task[]>(url, {
      cache: 'no-store'
    });
  }
}
