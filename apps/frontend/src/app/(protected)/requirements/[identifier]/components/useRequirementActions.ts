import { useCallback } from 'react';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import type {
  RequirementUpdate,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import type { UUID } from 'crypto';

/** Re-reads the requirement, or saves changes and then re-reads it. */
export function useRequirementActions(
  requirementId: UUID,
  onUpdated: (updated: RequirementWithMetrics) => void
) {
  const refresh = useCallback(async () => {
    const updated = await new RequirementClient().getRequirementWithMetrics(
      requirementId
    );
    onUpdated(updated);
  }, [requirementId, onUpdated]);

  const update = useCallback(
    async (changes: RequirementUpdate) => {
      await new RequirementClient().updateRequirement(requirementId, changes);
      await refresh();
    },
    [requirementId, refresh]
  );

  return { refresh, update };
}
