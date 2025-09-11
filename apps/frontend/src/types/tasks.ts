export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  creator_id: string;
  creator_name: string;
  assignee_id?: string;
  assignee_name?: string;
  entity_type: EntityType;
  entity_id: string;
  comment_id?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export type TaskStatus = 'Open' | 'In Progress' | 'Completed' | 'Cancelled';

export type TaskPriority = 'Low' | 'Medium' | 'High';

export type EntityType = 'Test' | 'TestSet' | 'TestRun' | 'TestResult' | 'Metric' | 'Model' | 'Prompt' | 'Task';

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

export interface TaskStats {
  total: number;
  open: number;
  in_progress: number;
  completed: number;
  cancelled: number;
}
