'use client';

import * as React from 'react';
import { useNotifications } from '@/components/common/NotificationContext';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { DeleteModal } from '@/components/common/DeleteModal';
import EntityCard, {
  type EntityCardFact,
  type EntityCardRelation,
} from '@/components/common/EntityCard';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import type { UUID } from 'crypto';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface RequirementCardProps {
  requirement: RequirementWithMetrics;
  onRefresh: () => void;
  onClick?: () => void;
  /** Retained for backward compatibility — no longer used in the card UI. */
  onEdit?: () => void;
  /** Retained for backward compatibility — no longer used in the card UI. */
  onDuplicate?: () => void;
  /** Retained for backward compatibility — no longer used in the card UI. */
  onViewMetrics?: () => void;
}

const plural = (n: number, one: string, many = `${one}s`) =>
  n === 1 ? one : many;

/** The parent, impact and linked counts, laid out for EntityCard. */
export function requirementCardSlots(
  requirement: Pick<
    RequirementWithMetrics,
    | 'impact'
    | 'parent'
    | 'children_count'
    | 'metrics'
    | 'test_counts'
    | 'examples_count'
    | 'sources'
  >
): {
  context?: string;
  facts: EntityCardFact[];
  relations: EntityCardRelation[];
} {
  const facts: EntityCardFact[] = [];
  const impact = requirement.impact?.type_value;
  if (impact) {
    facts.push({
      key: 'impact',
      kind: 'state',
      label: `${impact} impact`,
      tone: impact.toLowerCase() === 'minor' ? 'neutral' : 'warning',
    });
  }
  const children = requirement.children_count ?? 0;
  if (children > 0) {
    facts.push({
      key: 'children',
      kind: 'plain',
      label: `${children} ${plural(children, 'child', 'children')}`,
    });
  }

  const counts: [string, number, string][] = [
    ['metrics', requirement.metrics?.length ?? 0, 'metric'],
    ['tests', requirement.test_counts?.total ?? 0, 'test'],
    ['examples', requirement.examples_count ?? 0, 'example'],
    ['sources', requirement.sources?.length ?? 0, 'source'],
  ];
  return {
    context: requirement.parent?.name
      ? `${requirement.parent.name} ›`
      : undefined,
    facts,
    relations: counts.map(([key, count, noun]) => ({
      key,
      count,
      label: plural(count, noun),
    })),
  };
}

export default function RequirementCard({
  requirement,
  onRefresh,
  onClick,
}: RequirementCardProps) {
  const notifications = useNotifications();
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const handleConfirmDelete = async () => {
    try {
      setIsDeleting(true);
      const requirementClient = new RequirementClient();
      await requirementClient.deleteRequirement(requirement.id as UUID);

      notifications.show('Requirement deleted successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });

      onRefresh();
    } catch {
      notifications.show('Failed to delete requirement', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  const canDeleteRequirement = useCan(Capability.Requirement.DELETE);
  const metricsCount = requirement.metrics?.length || 0;
  const canDelete = canDeleteRequirement && metricsCount === 0;

  const slots = requirementCardSlots(requirement);

  return (
    <>
      <EntityCard
        title={requirement.name}
        description={requirement.description}
        onClick={onClick}
        onDelete={canDelete ? () => setDeleteDialogOpen(true) : undefined}
        userName={requirement.user?.name}
        userAvatar={requirement.user?.picture ?? undefined}
        updatedAt={requirement.updated_at}
        context={slots.context}
        facts={slots.facts}
        relations={slots.relations}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleConfirmDelete}
        isLoading={isDeleting}
        itemType="requirement"
        itemName={requirement.name}
      />
    </>
  );
}
