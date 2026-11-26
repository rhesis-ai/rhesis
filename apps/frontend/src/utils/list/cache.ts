import type { QueryClient, QueryKey } from '@tanstack/react-query';

/**
 * The first page of a list as it was last loaded, kept in the app's query
 * client so a return visit can draw it at once while the fresh page loads.
 * Entries live as long as the client keeps unused queries (`gcTime`).
 */
export interface CachedFirstPage<T> {
  data: T[];
  totalCount: number;
}

/** Whose data an entry is: a list returns different rows per user, org and project. */
export interface ListCacheScope {
  userId: string;
  organizationId: string;
  projectId: string;
}

// A descriptor built per parent entity (e.g. `entityTasksList(type, id)`) is a
// new object when that entity changes, and the list must refetch then. Number
// each identity so it can be part of a request fingerprint or cache key;
// callers memoize descriptors, so a stable list keeps a stable number.
const descriptorIds = new WeakMap<object, number>();
let nextDescriptorId = 0;

export function descriptorId(descriptor: object): number {
  let id = descriptorIds.get(descriptor);
  if (id === undefined) {
    id = nextDescriptorId++;
    descriptorIds.set(descriptor, id);
  }
  return id;
}

/** A list descriptor, as far as the cache needs one. */
type CachedList = object & { cacheId?: string };

function firstPageKey(descriptor: CachedList, scope: ListCacheScope): QueryKey {
  return [
    'list-first-page',
    descriptor.cacheId ?? descriptorId(descriptor),
    scope.userId,
    scope.organizationId,
    scope.projectId,
  ];
}

export function readFirstPage<T>(
  queryClient: QueryClient,
  descriptor: CachedList,
  scope: ListCacheScope
): CachedFirstPage<T> | undefined {
  return queryClient.getQueryData<CachedFirstPage<T>>(
    firstPageKey(descriptor, scope)
  );
}

export function writeFirstPage<T>(
  queryClient: QueryClient,
  descriptor: CachedList,
  scope: ListCacheScope,
  page: CachedFirstPage<T>
): void {
  queryClient.setQueryData(firstPageKey(descriptor, scope), page);
}
