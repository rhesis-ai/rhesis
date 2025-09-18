import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status, Priority } from '@/utils/api-client/interfaces/task';
import { Status as ApiStatus } from '@/utils/api-client/interfaces/status';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';

// Cache for statuses and priorities to avoid repeated API calls
let statusCache: Status[] | null = null;
let priorityCache: Priority[] | null = null;

export async function getStatuses(sessionToken?: string): Promise<Status[]> {
  if (statusCache) {
    return statusCache;
  }

  try {
    const token = sessionToken || getSessionToken();
    if (!token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(token);
    const statusClient = clientFactory.getStatusClient();
    const apiStatuses = await statusClient.getStatuses();
    
    // Convert API statuses to task statuses
    const statuses: Status[] = apiStatuses.map((status: ApiStatus) => ({
      id: status.id,
      name: status.name,
      description: status.description,
      entity_type_id: status.entity_type,
      created_at: new Date().toISOString(), // Default values since API doesn't have these
      updated_at: new Date().toISOString()
    }));
    
    statusCache = statuses;
    return statuses;
  } catch (error) {
    console.error('Failed to fetch statuses:', error);
    // Return default statuses if API fails - using proper UUIDs
    return [
      { id: '550e8400-e29b-41d4-a716-446655440001', name: 'Open', description: 'Task is open', entity_type_id: 'Task', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      { id: '550e8400-e29b-41d4-a716-446655440002', name: 'In Progress', description: 'Task is in progress', entity_type_id: 'Task', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      { id: '550e8400-e29b-41d4-a716-446655440003', name: 'Completed', description: 'Task is completed', entity_type_id: 'Task', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      { id: '550e8400-e29b-41d4-a716-446655440004', name: 'Cancelled', description: 'Task is cancelled', entity_type_id: 'Task', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
    ];
  }
}

export async function getPriorities(sessionToken?: string): Promise<Priority[]> {
  if (priorityCache) {
    return priorityCache;
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
      $filter: "type_name eq 'TaskPriority'"
    });
    
    // Convert API priorities to task priorities
    const priorities: Priority[] = apiPriorities.map((priority: TypeLookup) => ({
      id: priority.id,
      type_name: priority.type_name,
      type_value: priority.type_value,
      description: priority.description,
      created_at: new Date().toISOString(), // Default values since API doesn't have these
      updated_at: new Date().toISOString()
    }));
    
    priorityCache = priorities;
    return priorities;
  } catch (error) {
    console.error('Failed to fetch priorities:', error);
    // Return default priorities if API fails - using proper UUIDs
    return [
      { id: '550e8400-e29b-41d4-a716-446655440011', type_name: 'TaskPriority', type_value: 'Low', description: 'Low priority', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      { id: '550e8400-e29b-41d4-a716-446655440012', type_name: 'TaskPriority', type_value: 'Medium', description: 'Medium priority', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      { id: '550e8400-e29b-41d4-a716-446655440013', type_name: 'TaskPriority', type_value: 'High', description: 'High priority', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
    ];
  }
}

export async function getStatusByName(name: string, sessionToken?: string): Promise<Status | null> {
  const statuses = await getStatuses(sessionToken);
  return statuses.find(status => status.name === name) || null;
}

export async function getPriorityByName(name: string, sessionToken?: string): Promise<Priority | null> {
  const priorities = await getPriorities(sessionToken);
  return priorities.find(priority => priority.type_value === name) || null;
}

export function clearCache(): void {
  statusCache = null;
  priorityCache = null;
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
