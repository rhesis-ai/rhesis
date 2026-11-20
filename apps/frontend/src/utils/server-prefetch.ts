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
 * The capability check runs here: it's not just a render gate, it decides
 * whether the entity's data is embedded in the server-rendered payload at
 * all. The fetch starts at the same time as the check (see `startFetch`).
 * Callers should still gate the client render with the matching
 * `useCanWithStatus` check, so a user whose
 * permissions change mid-session gets a consistent client-side
 * `AccessDenied` without a full reload.
 *
 * Fails open to "no initial data" (never throws) so a permission-check or
 * upstream API error just falls back to the existing client-side fetch
 * instead of breaking the page.
 *
 * `fetchFirstPage` must be read-only: it runs even when the check then fails.
 */
export async function prefetchList<T>(
  capability: string | readonly string[],
  fetchFirstPage: () => Promise<PaginatedResponse<T>>
): Promise<PrefetchListResult<T>> {
  const response = startFetch(fetchFirstPage);
  if (!(await hasAnyServerCapability(capability))) {
    return { initialData: undefined, initialTotalCount: 0 };
  }

  try {
    const page = await response;
    return {
      // Server components pass data as props: strip class instances / non-plain
      // values so this doesn't blow up when serialized across the RSC boundary.
      initialData: JSON.parse(JSON.stringify(page.data)),
      initialTotalCount: page.pagination.totalCount,
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
 * Like `prefetchList`, `fetch` must be read-only.
 */
export async function prefetch<T>(
  capability: string | readonly string[],
  fetch: () => Promise<T>
): Promise<T | undefined> {
  const value = startFetch(fetch);
  if (!(await hasAnyServerCapability(capability))) return undefined;
  try {
    return JSON.parse(JSON.stringify(await value));
  } catch {
    return undefined;
  }
}

/** A tuple is OR'd, matching `useListAuthGate` (e.g. Annotations reads with
 * either TestResult.READ or Telemetry.READ). */
async function hasAnyServerCapability(
  capability: string | readonly string[]
): Promise<boolean> {
  const capabilities: readonly string[] =
    typeof capability === 'string' ? [capability] : capability;
  const checks = await Promise.all(capabilities.map(hasServerCapability));
  return checks.some(Boolean);
}

/**
 * Starts the fetch now so it runs alongside the capability check instead of
 * after it. When the check fails the result is thrown away, so it still never
 * reaches the page; the backend enforces the same permission on the request.
 */
function startFetch<T>(fetch: () => Promise<T>): Promise<T> {
  const promise = Promise.resolve().then(fetch);
  // Handled here so a dropped (unauthorized) fetch that rejects is not reported
  // as unhandled; the caller's own await still sees the rejection.
  promise.catch(() => undefined);
  return promise;
}
