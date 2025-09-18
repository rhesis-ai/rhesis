// Re-export from API client interfaces for backward compatibility
export type { 
  Task, 
  TaskCreate, 
  TaskUpdate, 
  TasksQueryParams,
  EntityType,
  TaskStats,
  User,
  Status,
  Priority
} from '@/utils/api-client/interfaces/task';

// Legacy types for backward compatibility (will be removed)
export type TaskStatus = 'Open' | 'In Progress' | 'Completed' | 'Cancelled';
export type TaskPriority = 'Low' | 'Medium' | 'High';

export interface CreateTaskRequest {
  title: string;
  description: string;
  priority: TaskPriority;
  assignee_id?: string;
  entity_type: EntityType;
  entity_id: string;
  comment_id?: string;
}

export interface UpdateTaskRequest {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: string;
}

export interface TaskFilters {
  status?: TaskStatus[];
  priority?: TaskPriority[];
  assignee_id?: string;
  entity_type?: EntityType[];
  created_after?: string;
  created_before?: string;
}
