/** Known fields in task_metadata - extensible via index signature */
export interface TaskMetadata {
  space_key?: string;
  [key: string]: unknown;
}

export interface Task {
  id: string;
  nano_id?: string;
  title: string;
  description?: string;
  user_id: string;
  assignee_id?: string;
  status_id: string;
  priority_id?: string;
  entity_id?: string;
  entity_type?: string;
  completed_at?: string;
  task_metadata?: TaskMetadata;
  total_comments?: number;
  organization_id?: string;
  tags?: Tag[];
  created_at?: string;
  updated_at?: string;

  // Relationships
  user?: User;
  assignee?: User;
  status?: Status;
  priority?: Priority;
}

export interface TaskCreate {
  title: string;
  description?: string;
  assignee_id?: string | null;
  status_id: string;
  priority_id?: string | null;
  entity_id?: string;
  entity_type?: string;
  completed_at?: string;
  task_metadata?: TaskMetadata;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  assignee_id?: string | null;
  status_id?: string;
  priority_id?: string | null;
  entity_id?: string;
  entity_type?: string;
  completed_at?: string;
  task_metadata?: TaskMetadata;
}

export interface TasksQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: string;
  $filter?: string;
}

export interface TaskStats {
  total: number;
  open: number;
  inProgress: number;
  completed: number;
  cancelled: number;
}

export interface User {
  id: string;
  name: string;
  email: string;
  picture?: string;
}

export interface Status {
  id: string;
  name: string;
  description?: string;
  entity_type_id?: string;
}

export interface Priority {
  id: string;
  type_name?: string;
  type_value?: string;
  description?: string;
}

export interface Tag {
  id: string;
  name: string;
  description?: string;
  color?: string;
}

export type EntityType =
  | 'Test'
  | 'TestSet'
  | 'TestRun'
  | 'TestResult'
  | 'Task'
  | 'Source';
