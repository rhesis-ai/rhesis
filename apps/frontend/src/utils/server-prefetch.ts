import { hasServerCapability } from './server-permissions';
import type { PaginatedResponse } from './api-client/interfaces/pagination';

export interface PrefetchListResult<T> {
  /** Undefined when unauthorized or the fetch failed -- caller falls back to a client fetch. */
  initialData?: T[];
  initialTotalCount: number;
}

/**
 * Server-side counterpart of `usePaginatedList`: fetches a directory page's
 * first page during server rendering so the page arrives with content
 * already in place, with no client-side spinner on first load.
 *
 * The capability check runs here, before the fetch: it's not just a render
 * gate, it decides whether the entity's data is fetched and embedded in the
 * server-rendered payload at all. Callers should still gate the client
 * render with the matching `useCanWithStatus` check, so a user whose
 * permissions change mid-session gets a consistent client-side
 * `AccessDenied` without a full reload.
 *
 * Fails open to "no initial data" (never throws) so a permission-check or
 * upstream API error just falls back to the existing client-side fetch
 * instead of breaking the page.
 */
export async function prefetchList<T>(
  capability: string,
  fetchFirstPage: () => Promise<PaginatedResponse<T>>
): Promise<PrefetchListResult<T>> {
  const canRead = await hasServerCapability(capability);
  if (!canRead) {
    return { initialData: undefined, initialTotalCount: 0 };
  }

  try {
    const response = await fetchFirstPage();
    return {
      // Server components pass data as props: strip class instances / non-plain
      // values so this doesn't blow up when serialized across the RSC boundary.
      initialData: JSON.parse(JSON.stringify(response.data)),
      initialTotalCount: response.pagination.totalCount,
    };
  } catch {
    return { initialData: undefined, initialTotalCount: 0 };
  }
}
