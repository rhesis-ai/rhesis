export type {
  Task,
  TaskCreate,
  TaskUpdate,
  TasksQueryParams,
  EntityType,
  User,
  Status,
  Priority,
} from '@/utils/api-client/interfaces/task';

// Legacy types for backward compatibility (will be removed)
export type TaskStatus = 'Open' | 'In Progress' | 'Completed' | 'Cancelled';
export type TaskPriority = 'Low' | 'Medium' | 'High';
