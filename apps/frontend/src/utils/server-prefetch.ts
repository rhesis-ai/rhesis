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
  capability: string | readonly string[],
  fetchFirstPage: () => Promise<PaginatedResponse<T>>
): Promise<PrefetchListResult<T>> {
  // A tuple is OR'd, matching `useListAuthGate` (e.g. Annotations reads with
  // either TestResult.READ or Telemetry.READ).
  const capabilities: readonly string[] =
    typeof capability === 'string' ? [capability] : capability;
  const checks = await Promise.all(capabilities.map(hasServerCapability));
  if (!checks.some(Boolean)) {
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

/**
 * `prefetchList` for a single value: a detail record, an unpaginated list, a
 * lookup. Same contract -- capability-gated (a tuple is OR'd), never throws,
 * `undefined` means "let the client fetch it" -- and the result is passed to
 * the client component as an `initial*` prop that seeds its existing hook.
 */
export async function prefetch<T>(
  capability: string | readonly string[],
  fetch: () => Promise<T>
): Promise<T | undefined> {
  const capabilities: readonly string[] =
    typeof capability === 'string' ? [capability] : capability;
  const checks = await Promise.all(capabilities.map(hasServerCapability));
  if (!checks.some(Boolean)) return undefined;
  try {
    return JSON.parse(JSON.stringify(await fetch()));
  } catch {
    return undefined;
  }
}
