import { UUID } from 'crypto';
import { User } from './user';

/**
 * Type of operation performed on an entity
 */
export enum ActivityOperation {
  CREATE = 'create',
  UPDATE = 'update',
  DELETE = 'delete',
}

/**
 * Time range for bulk operations
 */
export interface TimeRange {
  start: string; // ISO datetime string
  end: string; // ISO datetime string
}

/**
 * A single activity item or grouped bulk operation
 */
export interface ActivityItem {
  entity_type: string;
  entity_id: UUID | null; // Null for bulk operations
  operation: ActivityOperation;
  timestamp: string; // ISO datetime string
  user: User | null;
  entity_data: Record<string, unknown> | null; // Null for bulk operations

  // Bulk operation fields
  is_bulk: boolean;
  count?: number; // Number of entities in bulk operation
  time_range?: TimeRange; // Time span of bulk operation
  summary?: string; // Human-readable summary (e.g., "50 Tests created by Harry Cruz")
  entity_ids?: UUID[]; // All entity IDs in bulk
  sample_entities?: Record<string, unknown>[]; // First few entities as preview
}

/**
 * Response containing recent activities across all trackable entities
 */
export interface RecentActivitiesResponse {
  activities: ActivityItem[];
  total: number; // Total number of activity groups (not individual activities)
}
