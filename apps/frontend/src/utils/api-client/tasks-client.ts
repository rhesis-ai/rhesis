import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Task,
  TaskBulkDeleteResponse,
  TaskCreate,
  TaskUpdate,
  TasksQueryParams,
} from './interfaces/task';
import { PaginatedResponse } from './interfaces/pagination';

export class TasksClient extends BaseApiClient {
  constructor(sessionToken?: string, retryConfig = {}, projectId?: string) {
    super(sessionToken, retryConfig, projectId);
  }

  async getTasks(
    params: TasksQueryParams = {}
  ): Promise<PaginatedResponse<Task>> {
    return this.fetchPaginated<Task>(API_ENDPOINTS.tasks, {
      skip: params.skip ?? 0,
      limit: params.limit ?? 10,
      sort_by: params.sort_by,
      sort_order: params.sort_order as 'asc' | 'desc' | undefined,
      $filter: params.$filter,
    });
  }

  async getTask(taskId: string): Promise<Task> {
    const response = await this.fetch<Task>(`${API_ENDPOINTS.tasks}/${taskId}`);
    return response;
  }

  async createTask(taskData: TaskCreate): Promise<Task> {
    const response = await this.fetch<Task>(`${API_ENDPOINTS.tasks}/`, {
      method: 'POST',
      body: JSON.stringify(taskData),
    });
    return response;
  }

  async updateTask(taskId: string, taskData: TaskUpdate): Promise<Task> {
    const response = await this.fetch<Task>(
      `${API_ENDPOINTS.tasks}/${taskId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(taskData),
      }
    );
    return response;
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.fetch<void>(`${API_ENDPOINTS.tasks}/${taskId}`, {
      method: 'DELETE',
    });
  }

  async bulkDeleteTasks(taskIds: string[]): Promise<TaskBulkDeleteResponse> {
    return this.bulkDelete<TaskBulkDeleteResponse>(
      API_ENDPOINTS.tasks,
      'task_ids',
      taskIds
    );
  }

  async getTasksByEntity(
    entityType: string,
    entityId: string,
    params: TasksQueryParams = {}
  ): Promise<PaginatedResponse<Task>> {
    return this.fetchPaginated<Task>(
      `${API_ENDPOINTS.tasks}/${entityType}/${entityId}`,
      {
        skip: params.skip ?? 0,
        limit: params.limit ?? 10,
        sort_by: params.sort_by,
        sort_order: params.sort_order as 'asc' | 'desc' | undefined,
      }
    );
  }

  async getTasksByCommentId(
    commentId: string,
    params: TasksQueryParams = {}
  ): Promise<Task[]> {
    // Since OData filtering on JSON fields is not supported by the backend,
    // we'll fetch all tasks and filter on the frontend as a temporary solution
    const { data: allTasks } = await this.getTasks({
      limit: 100,
      sort_by: params.sort_by,
      sort_order: params.sort_order,
    });

    // Filter tasks on the frontend by checking task_metadata.comment_id
    const filteredTasks = allTasks.filter(
      task => task.task_metadata && task.task_metadata.comment_id === commentId
    );

    return filteredTasks;
  }
}
