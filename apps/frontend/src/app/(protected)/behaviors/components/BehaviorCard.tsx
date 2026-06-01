'use client';

import * as React from 'react';
import { useNotifications } from '@/components/common/NotificationContext';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { DeleteModal } from '@/components/common/DeleteModal';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';

interface BehaviorCardProps {
  behavior: BehaviorWithMetrics;
  onRefresh: () => void;
  sessionToken: string;
  /** Retained for backward compatibility — no longer used in the card UI. */
  onEdit?: () => void;
  /** Retained for backward compatibility — no longer used in the card UI. */
  onDuplicate?: () => void;
  /** Retained for backward compatibility — no longer used in the card UI. */
  onViewMetrics?: () => void;
}

export default function BehaviorCard({
  behavior,
  onRefresh,
  sessionToken,
}: BehaviorCardProps) {
  const notifications = useNotifications();
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const handleConfirmDelete = async () => {
    try {
      setIsDeleting(true);
      const behaviorClient = new BehaviorClient(sessionToken);
      await behaviorClient.deleteBehavior(behavior.id as UUID);

      notifications.show('Behavior deleted successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });

      onRefresh();
    } catch {
      notifications.show('Failed to delete behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  const metricsCount = behavior.metrics?.length || 0;
  const canDelete = metricsCount === 0;

  const tags = behavior.tags ?? [];
  const tagsCount = tags.length;
  const MAX_VISIBLE_TAGS = 5;

  const chipSections: ChipSection[] = [
    {
      label: 'Metrics',
      chips: [
        ...(behavior.metrics || []).slice(0, 3).map(metric => ({
          key: metric.id,
          label: metric.name,
          maxWidth: '150px',
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
          maxWidth: '150px',
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
        title={behavior.name}
        description={behavior.description || 'No description provided'}
        onDelete={canDelete ? () => setDeleteDialogOpen(true) : undefined}
        status={behavior.status?.name}
        userName={behavior.user?.name}
        chipSections={chipSections}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleConfirmDelete}
        isLoading={isDeleting}
        itemType="behavior"
        itemName={behavior.name}
      />
    </>
  );
}
