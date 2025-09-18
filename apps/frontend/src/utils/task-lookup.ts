import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status, Priority } from '@/utils/api-client/interfaces/task';

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
    const statuses = await statusClient.getStatuses();
    
    statusCache = statuses;
    return statuses;
  } catch (error) {
    console.error('Failed to fetch statuses:', error);
    // Return default statuses if API fails
    return [
      { id: 'default-open', name: 'Open', description: 'Task is open' },
      { id: 'default-in-progress', name: 'In Progress', description: 'Task is in progress' },
      { id: 'default-completed', name: 'Completed', description: 'Task is completed' },
      { id: 'default-cancelled', name: 'Cancelled', description: 'Task is cancelled' },
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
    const priorities = await typeLookupClient.getTypeLookups({
      $filter: "type eq 'TaskPriority'"
    });
    
    priorityCache = priorities;
    return priorities;
  } catch (error) {
    console.error('Failed to fetch priorities:', error);
    // Return default priorities if API fails
    return [
      { id: 'default-low', name: 'Low', description: 'Low priority' },
      { id: 'default-medium', name: 'Medium', description: 'Medium priority' },
      { id: 'default-high', name: 'High', description: 'High priority' },
    ];
  }
}

export async function getStatusByName(name: string, sessionToken?: string): Promise<Status | null> {
  const statuses = await getStatuses(sessionToken);
  return statuses.find(status => status.name === name) || null;
}

export async function getPriorityByName(name: string, sessionToken?: string): Promise<Priority | null> {
  const priorities = await getPriorities(sessionToken);
  return priorities.find(priority => priority.name === name) || null;
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
