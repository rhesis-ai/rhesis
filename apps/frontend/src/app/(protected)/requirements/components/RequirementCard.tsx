'use client';

import * as React from 'react';
import { useNotifications } from '@/components/common/NotificationContext';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { DeleteModal } from '@/components/common/DeleteModal';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
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

  const tags = requirement.tags ?? [];
  const tagsCount = tags.length;
  const MAX_VISIBLE_TAGS = 5;

  const chipSections: ChipSection[] = [
    {
      label: 'Metrics',
      chips: [
        ...(requirement.metrics || []).slice(0, 3).map(metric => ({
          key: metric.id,
          label: metric.name,
        })),
        ...(metricsCount > 3
          ? [{ key: 'more', label: `+${metricsCount - 3} more` }]
          : []),
      ],
      emptyText: 'No metrics assigned',
    },
    {
      label: 'Tags',
      chips: [
        ...tags.slice(0, MAX_VISIBLE_TAGS).map(tag => ({
          key: tag.id,
          label: tag.name,
        })),
        ...(tagsCount > MAX_VISIBLE_TAGS
          ? [
              {
                key: 'more-tags',
                label: `+${tagsCount - MAX_VISIBLE_TAGS} more`,
              },
            ]
          : []),
      ],
      emptyText: 'No tags assigned',
    },
  ];

  return (
    <>
      <EntityCard
        title={requirement.name}
        description={requirement.description || 'No description provided'}
        onClick={onClick}
        onDelete={canDelete ? () => setDeleteDialogOpen(true) : undefined}
        userName={requirement.user?.name}
        chipSections={chipSections}
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
