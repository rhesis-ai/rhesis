import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status, Priority } from '@/utils/api-client/interfaces/task';
import { Status as ApiStatus } from '@/utils/api-client/interfaces/status';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';

/**
 * Proper cache class with TTL (Time To Live) support
 */
class TaskDataCache {
  private cache = new Map<string, { data: any; timestamp: number }>();
  private readonly TTL = 5 * 60 * 1000; // 5 minutes

  get<T>(key: string): T | null {
    const item = this.cache.get(key);
    if (!item || Date.now() - item.timestamp > this.TTL) {
      this.cache.delete(key);
      return null;
    }
    return item.data;
  }

  set<T>(key: string, data: T): void {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  clear(): void {
    this.cache.clear();
  }

  has(key: string): boolean {
    const item = this.cache.get(key);
    return item ? Date.now() - item.timestamp <= this.TTL : false;
  }
}

// Create a singleton cache instance
const taskDataCache = new TaskDataCache();

export async function getStatuses(sessionToken?: string): Promise<Status[]> {
  const cacheKey = 'statuses';
  const cachedStatuses = taskDataCache.get<Status[]>(cacheKey);
  if (cachedStatuses) {
    return cachedStatuses;
  }

  try {
    const token = sessionToken || getSessionToken();
    if (!token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(token);
    const statusClient = clientFactory.getStatusClient();
    const apiStatuses = await statusClient.getStatuses({ entity_type: 'Task' });

    // Convert API statuses to task statuses and filter for specific options
    const allowedStatusNames = [
      'Open',
      'In Progress',
      'Completed',
      'Cancelled',
    ];
    const statuses: Status[] = apiStatuses
      .filter((status: ApiStatus) => allowedStatusNames.includes(status.name))
      .map((status: ApiStatus) => ({
        id: status.id,
        name: status.name,
        description: status.description,
        entity_type_id: status.entity_type,
      }));

    taskDataCache.set(cacheKey, statuses);
    return statuses;
  } catch (_error) {
    // Return default statuses if API fails - using proper UUIDs
    const defaultStatuses = [
      {
        id: '550e8400-e29b-41d4-a716-446655440001',
        name: 'Open',
        description: 'Task is open',
        entity_type_id: 'Task',
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440002',
        name: 'In Progress',
        description: 'Task is in progress',
        entity_type_id: 'Task',
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440003',
        name: 'Completed',
        description: 'Task is completed',
        entity_type_id: 'Task',
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440004',
        name: 'Cancelled',
        description: 'Task is cancelled',
        entity_type_id: 'Task',
      },
    ];
    taskDataCache.set(cacheKey, defaultStatuses);
    return defaultStatuses;
  }
}

export async function getPriorities(
  sessionToken?: string
): Promise<Priority[]> {
  const cacheKey = 'priorities';
  const cachedPriorities = taskDataCache.get<Priority[]>(cacheKey);
  if (cachedPriorities) {
    return cachedPriorities;
  }

  try {
    const token = sessionToken || getSessionToken();
    if (!token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(token);
    const typeLookupClient = clientFactory.getTypeLookupClient();

    // Filter for task priorities (assuming they have a specific type or filter)
    const apiPriorities = await typeLookupClient.getTypeLookups({
      $filter: "type_name eq 'TaskPriority'",
    });

    // Convert API priorities to task priorities and filter for specific options
    const allowedPriorityValues = ['Low', 'Medium', 'High'];
    const priorities: Priority[] = apiPriorities
      .filter((priority: TypeLookup) =>
        allowedPriorityValues.includes(priority.type_value)
      )
      .map((priority: TypeLookup) => ({
        id: priority.id,
        type_name: priority.type_name,
        type_value: priority.type_value,
        description: priority.description,
      }));

    taskDataCache.set(cacheKey, priorities);
    return priorities;
  } catch (_error) {
    // Return default priorities if API fails - using proper UUIDs
    const defaultPriorities = [
      {
        id: '550e8400-e29b-41d4-a716-446655440011',
        type_name: 'TaskPriority',
        type_value: 'Low',
        description: 'Low priority',
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440012',
        type_name: 'TaskPriority',
        type_value: 'Medium',
        description: 'Medium priority',
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440013',
        type_name: 'TaskPriority',
        type_value: 'High',
        description: 'High priority',
      },
    ];
    taskDataCache.set(cacheKey, defaultPriorities);
    return defaultPriorities;
  }
}

export async function getStatusByName(
  name: string,
  sessionToken?: string
): Promise<Status | null> {
  const statuses = await getStatuses(sessionToken);
  return statuses.find(status => status.name === name) || null;
}

export async function getPriorityByName(
  name: string,
  sessionToken?: string
): Promise<Priority | null> {
  const priorities = await getPriorities(sessionToken);
  return priorities.find(priority => priority.type_value === name) || null;
}

export async function getStatusesForTask(
  sessionToken?: string,
  existingTaskStatusId?: string
): Promise<Status[]> {
  const allStatuses = await getStatuses(sessionToken);

  // If we have an existing task status ID that's not in our filtered list, include it
  if (
    existingTaskStatusId &&
    !allStatuses.find(status => status.id === existingTaskStatusId)
  ) {
    try {
      const token = sessionToken || getSessionToken();
      if (token) {
        const clientFactory = new ApiClientFactory(token);
        const statusClient = clientFactory.getStatusClient();
        const specificStatus =
          await statusClient.getStatus(existingTaskStatusId);

        if (specificStatus) {
          const additionalStatus: Status = {
            id: specificStatus.id,
            name: specificStatus.name,
            description: specificStatus.description,
            entity_type_id: specificStatus.entity_type,
          };
          return [...allStatuses, additionalStatus];
        }
      }
    } catch (_error) {}
  }

  return allStatuses;
}

export async function getPrioritiesForTask(
  sessionToken?: string,
  existingTaskPriorityId?: string
): Promise<Priority[]> {
  const allPriorities = await getPriorities(sessionToken);

  // If we have an existing task priority ID that's not in our filtered list, include it
  if (
    existingTaskPriorityId &&
    !allPriorities.find(priority => priority.id === existingTaskPriorityId)
  ) {
    try {
      const token = sessionToken || getSessionToken();
      if (token) {
        const clientFactory = new ApiClientFactory(token);
        const typeLookupClient = clientFactory.getTypeLookupClient();
        const specificPriority = await typeLookupClient.getTypeLookup(
          existingTaskPriorityId
        );

        if (specificPriority) {
          const additionalPriority: Priority = {
            id: specificPriority.id,
            type_name: specificPriority.type_name,
            type_value: specificPriority.type_value,
            description: specificPriority.description,
          };
          return [...allPriorities, additionalPriority];
        }
      }
    } catch (_error) {}
  }

  return allPriorities;
}

export function clearCache(): void {
  taskDataCache.clear();
}

// Helper function to get session token from NextAuth
function getSessionToken(): string | null {
  // Try to get from NextAuth session cookie
  if (typeof document !== 'undefined') {
    const cookies = document.cookie.split(';');
    const sessionCookie = cookies.find(cookie =>
      cookie.trim().startsWith('next-auth.session-token=')
    );
    if (sessionCookie) {
      return sessionCookie.split('=')[1];
    }
  }
  return null;
}
