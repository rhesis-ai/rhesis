'use client';

import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useEndpoints } from '@/hooks/useEndpoints';

interface ProjectNeedsEndpoint {
  /** The check is still running — callers should render neither branch yet. */
  pending: boolean;
  /** Known to have zero endpoints, so nothing can be tested yet. */
  needsEndpoint: boolean;
}

/**
 * Whether the active project still has no endpoint. Drives the Architect
 * welcome screen: getting-started cards instead of suggestion chips, since a
 * prompt cannot run anywhere until an endpoint exists.
 *
 * `pending` keeps callers from flashing one branch before the other — both the
 * chips and the help cards wait for the same answer.
 */
export function useProjectNeedsEndpoint(): ProjectNeedsEndpoint {
  const { activeProject } = useActiveProject();
  const enabled = !!activeProject?.id;

  // limit: 1 — existence check only. Requests carry X-Project-Id, so this is
  // already scoped to the active project. react-query dedupes the shared key
  // across every caller, so asking twice costs one request.
  const {
    data: endpoints,
    isSuccess,
    isPending,
  } = useEndpoints({ limit: 1 }, enabled);

  // `isPending`, not `!isSuccess`: a failed query leaves isSuccess false for
  // good, which would latch `pending` on and hide the chips and the cards
  // together, forever. Falling back to "not onboarding" degrades to the plain
  // welcome screen — the same thing a project with an endpoint sees.
  //
  // With no project there is nothing to prompt about, so leave the default UI
  // alone there too.
  return {
    pending: enabled && isPending,
    needsEndpoint: enabled && isSuccess && endpoints?.length === 0,
  };
}
