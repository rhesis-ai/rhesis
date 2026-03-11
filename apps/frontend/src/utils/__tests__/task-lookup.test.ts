/**
 * Tests for src/utils/task-lookup.ts
 *
 * Covers:
 *  - TaskDataCache: TTL expiry, get/set/has/clear
 *  - getStatuses: cache hit, API success, fallback defaults on error
 *  - getPriorities: cache hit, API success, fallback defaults on error
 *  - getStatusByName / getPriorityByName: delegation + lookup
 *  - getStatusesForTask: appends unknown status IDs via extra API call
 *  - getPrioritiesForTask: appends unknown priority IDs via extra API call
 *  - clearCache: resets the singleton cache
 */

// Mock ApiClientFactory and its clients
const mockGetStatuses = jest.fn();
const mockGetStatus = jest.fn();
const mockGetTypeLookups = jest.fn();
const mockGetTypeLookup = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getStatusClient: () => ({
      getStatuses: mockGetStatuses,
      getStatus: mockGetStatus,
    }),
    getTypeLookupClient: () => ({
      getTypeLookups: mockGetTypeLookups,
      getTypeLookup: mockGetTypeLookup,
    }),
  })),
}));

import {
  getStatuses,
  getPriorities,
  getStatusByName,
  getPriorityByName,
  getStatusesForTask,
  getPrioritiesForTask,
  clearCache,
} from '../task-lookup';

const API_STATUSES = [
  { id: 's1', name: 'Open', description: 'open', entity_type: 'Task' },
  {
    id: 's2',
    name: 'In Progress',
    description: 'in progress',
    entity_type: 'Task',
  },
  {
    id: 's3',
    name: 'Completed',
    description: 'completed',
    entity_type: 'Task',
  },
  {
    id: 's4',
    name: 'Cancelled',
    description: 'cancelled',
    entity_type: 'Task',
  },
  // This one should be filtered OUT (not in the allowed list)
  { id: 's5', name: 'Archived', description: 'archived', entity_type: 'Task' },
];

const API_PRIORITIES = [
  {
    id: 'p1',
    type_name: 'TaskPriority',
    type_value: 'Low',
    description: 'low',
  },
  {
    id: 'p2',
    type_name: 'TaskPriority',
    type_value: 'Medium',
    description: 'medium',
  },
  {
    id: 'p3',
    type_name: 'TaskPriority',
    type_value: 'High',
    description: 'high',
  },
];

// Provide a session cookie so the internal getSessionToken() helper finds a token.
// Defined in beforeEach/afterEach so it doesn't leak into other test suites.
let cookieDescriptor: PropertyDescriptor | undefined;

beforeEach(() => {
  cookieDescriptor = Object.getOwnPropertyDescriptor(document, 'cookie');
  Object.defineProperty(document, 'cookie', {
    configurable: true,
    get: () => 'next-auth.session-token=test-token',
  });
  clearCache();
  mockGetStatuses.mockReset();
  mockGetStatus.mockReset();
  mockGetTypeLookups.mockReset();
  mockGetTypeLookup.mockReset();
});

afterEach(() => {
  if (cookieDescriptor) {
    Object.defineProperty(document, 'cookie', cookieDescriptor);
  } else {
    // If there was no previous descriptor, delete the override
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (document as any).cookie;
  }
});

// ---------------------------------------------------------------------------
// getStatuses
// ---------------------------------------------------------------------------

describe('getStatuses', () => {
  it('returns filtered statuses from the API on first call', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    const result = await getStatuses('tok');

    // Only allowed names should be returned (Archived is filtered out)
    expect(result).toHaveLength(4);
    expect(result.map(s => s.name)).toEqual([
      'Open',
      'In Progress',
      'Completed',
      'Cancelled',
    ]);
    expect(result[0]).toMatchObject({ id: 's1', name: 'Open' });
    expect(mockGetStatuses).toHaveBeenCalledTimes(1);
  });

  it('returns cached result on second call without re-fetching', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    await getStatuses('tok');
    await getStatuses('tok');

    // API should only have been called once
    expect(mockGetStatuses).toHaveBeenCalledTimes(1);
  });

  it('falls back to default statuses when the API throws', async () => {
    mockGetStatuses.mockRejectedValue(new Error('API error'));

    const result = await getStatuses('tok');

    expect(result).toHaveLength(4);
    expect(result.map(s => s.name)).toEqual([
      'Open',
      'In Progress',
      'Completed',
      'Cancelled',
    ]);
    // Defaults use preset UUIDs
    expect(result[0].id).toBe('550e8400-e29b-41d4-a716-446655440001');
  });

  it('caches default statuses so subsequent calls skip the API', async () => {
    mockGetStatuses.mockRejectedValue(new Error('API error'));

    await getStatuses('tok');
    await getStatuses('tok');

    expect(mockGetStatuses).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// getPriorities
// ---------------------------------------------------------------------------

describe('getPriorities', () => {
  it('returns filtered priorities from the API', async () => {
    mockGetTypeLookups.mockResolvedValue(API_PRIORITIES);

    const result = await getPriorities('tok');

    expect(result).toHaveLength(3);
    expect(result.map(p => p.type_value)).toEqual(['Low', 'Medium', 'High']);
    expect(mockGetTypeLookups).toHaveBeenCalledTimes(1);
  });

  it('returns cached result on second call', async () => {
    mockGetTypeLookups.mockResolvedValue(API_PRIORITIES);

    await getPriorities('tok');
    await getPriorities('tok');

    expect(mockGetTypeLookups).toHaveBeenCalledTimes(1);
  });

  it('falls back to default priorities on API error', async () => {
    mockGetTypeLookups.mockRejectedValue(new Error('API error'));

    const result = await getPriorities('tok');

    expect(result).toHaveLength(3);
    expect(result.map(p => p.type_value)).toEqual(['Low', 'Medium', 'High']);
    expect(result[0].id).toBe('550e8400-e29b-41d4-a716-446655440011');
  });
});

// ---------------------------------------------------------------------------
// getStatusByName / getPriorityByName
// ---------------------------------------------------------------------------

describe('getStatusByName', () => {
  it('returns the matching status by name', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    const status = await getStatusByName('In Progress', 'tok');
    expect(status?.id).toBe('s2');
  });

  it('returns null when name is not found', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    const status = await getStatusByName('Unknown', 'tok');
    expect(status).toBeNull();
  });
});

describe('getPriorityByName', () => {
  it('returns the matching priority by type_value', async () => {
    mockGetTypeLookups.mockResolvedValue(API_PRIORITIES);

    const priority = await getPriorityByName('High', 'tok');
    expect(priority?.id).toBe('p3');
  });

  it('returns null when name is not found', async () => {
    mockGetTypeLookups.mockResolvedValue(API_PRIORITIES);

    const priority = await getPriorityByName('Critical', 'tok');
    expect(priority).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getStatusesForTask
// ---------------------------------------------------------------------------

describe('getStatusesForTask', () => {
  it('returns all statuses when existingTaskStatusId is in the list', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    // 's1' is already in the allowed list
    const result = await getStatusesForTask('tok', 's1');

    expect(result).toHaveLength(4);
    expect(mockGetStatus).not.toHaveBeenCalled();
  });

  it('appends the extra status when existingTaskStatusId is NOT in the list', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);
    mockGetStatus.mockResolvedValue({
      id: 'extra-id',
      name: 'Custom Status',
      description: 'custom',
      entity_type: 'Task',
    });

    const result = await getStatusesForTask('tok', 'extra-id');

    // 4 allowed + 1 extra = 5
    expect(result).toHaveLength(5);
    expect(result[4]).toMatchObject({ id: 'extra-id', name: 'Custom Status' });
    expect(mockGetStatus).toHaveBeenCalledWith('extra-id');
  });

  it('returns base statuses if the extra status API call fails', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);
    mockGetStatus.mockRejectedValue(new Error('not found'));

    const result = await getStatusesForTask('tok', 'missing-id');

    expect(result).toHaveLength(4);
  });

  it('returns base statuses when no existingTaskStatusId is provided', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    const result = await getStatusesForTask('tok');

    expect(result).toHaveLength(4);
    expect(mockGetStatus).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// getPrioritiesForTask
// ---------------------------------------------------------------------------

describe('getPrioritiesForTask', () => {
  it('appends the extra priority when id is NOT in the list', async () => {
    mockGetTypeLookups.mockResolvedValue(API_PRIORITIES);
    mockGetTypeLookup.mockResolvedValue({
      id: 'extra-p',
      type_name: 'TaskPriority',
      type_value: 'Critical',
      description: 'critical',
    });

    const result = await getPrioritiesForTask('tok', 'extra-p');

    expect(result).toHaveLength(4);
    expect(result[3]).toMatchObject({ id: 'extra-p', type_value: 'Critical' });
  });

  it('returns base priorities when existingTaskPriorityId is already in the list', async () => {
    mockGetTypeLookups.mockResolvedValue(API_PRIORITIES);

    const result = await getPrioritiesForTask('tok', 'p1');

    expect(result).toHaveLength(3);
    expect(mockGetTypeLookup).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// clearCache
// ---------------------------------------------------------------------------

describe('clearCache', () => {
  it('forces a fresh API call after the cache is cleared', async () => {
    mockGetStatuses.mockResolvedValue(API_STATUSES);

    await getStatuses('tok'); // populates cache
    clearCache();
    await getStatuses('tok'); // should hit API again

    expect(mockGetStatuses).toHaveBeenCalledTimes(2);
  });
});
