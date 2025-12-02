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
 * A single activity item representing a CRUD operation on an entity
 */
export interface ActivityItem {
  entity_type: string;
  entity_id: UUID;
  operation: ActivityOperation;
  timestamp: string; // ISO datetime string
  user: User | null;
  entity_data: Record<string, any>;
}

/**
 * Response containing recent activities across all trackable entities
 */
export interface RecentActivitiesResponse {
  activities: ActivityItem[];
  total: number;
}
