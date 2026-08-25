import type { WithPermittedActions } from '@/types/affordances';

/** Known fields in task_metadata - extensible via index signature */
export interface TaskMetadata {
  space_key?: string;
  [key: string]: unknown;
}

export interface Task extends WithPermittedActions {
  id: string;
  nano_id?: string;
  title: string;
  description?: string;
  assignee_id?: string;
  status_id: string;
  priority_id?: string;
  entity_id?: string;
  entity_type?: string;
  task_metadata?: TaskMetadata;
  created_at?: string;

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

export interface User {
  id: string;
  name: string;
  email: string;
  picture?: string;
}

export interface Status {
  id: string;
  name: string;
}

export interface Priority {
  id: string;
  type_value?: string;
}

// Entity types are defined canonically in `@/types/entity-type` and re-exported
// here for backward compatibility.
export { EntityType } from '@/types/entity-type';

export interface TaskBulkDeleteResponse {
  deleted_ids: string[];
  not_found_ids: string[];
  forbidden_ids: string[];
}
