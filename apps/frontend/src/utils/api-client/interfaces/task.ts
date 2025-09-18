import { UUID } from 'crypto';

// Base interfaces matching backend schemas
export interface TaskBase {
  title: string;
  description?: string;
  creator_id: UUID;
  assignee_id?: UUID;
  status_id: UUID;
  priority_id?: UUID;
  entity_id?: UUID;
  entity_type?: string;
  completed_at?: string;
  task_metadata?: Record<string, any>;
}

export interface TaskCreate {
  title: string;
  description?: string;
  creator_id?: UUID; // Auto-populated from authenticated user
  assignee_id?: UUID;
  status_id: UUID;
  priority_id?: UUID;
  entity_id?: UUID;
  entity_type?: string;
  completed_at?: string;
  task_metadata?: Record<string, any>;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  assignee_id?: UUID;
  status_id?: UUID;
  priority_id?: UUID;
  completed_at?: string;
  task_metadata?: Record<string, any>;
}

// User interface for relationships
export interface User {
  id: UUID;
  name?: string;
  email?: string;
  picture?: string;
}

// Status interface for relationships
export interface Status {
  id: UUID;
  name: string;
  description?: string;
}

// Priority interface (TypeLookup)
export interface Priority {
  id: UUID;
  name: string;
  description?: string;
}

// Complete Task interface with relationships
export interface Task extends TaskBase {
  id: UUID;
  nano_id?: string;
  created_at: string;
  updated_at: string;
  organization_id?: UUID;
  user_id?: UUID;
  total_comments?: number;

  // Relationships
  creator?: User;
  assignee?: User;
  status?: Status;
  priority?: Priority;
}

// Query parameters for task listing
export interface TasksQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
}

// Entity types that tasks can be associated with
export type EntityType = 'Test' | 'TestSet' | 'TestRun' | 'TestResult' | 'Comment' | 'Task';

// Task statistics
export interface TaskStats {
  total: number;
  open: number;
  in_progress: number;
  completed: number;
  cancelled: number;
}
