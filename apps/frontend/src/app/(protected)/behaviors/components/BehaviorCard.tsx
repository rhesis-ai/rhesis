'use client';

import * as React from 'react';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import EditIcon from '@mui/icons-material/Edit';
import AssessmentIcon from '@mui/icons-material/Assessment';
import DeleteIcon from '@mui/icons-material/Delete';
import { PsychologyIcon, AutoGraphIcon } from '@/components/icons';
import { useTheme } from '@mui/material/styles';
import { useNotifications } from '@/components/common/NotificationContext';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { DeleteModal } from '@/components/common/DeleteModal';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';

interface BehaviorCardProps {
  behavior: BehaviorWithMetrics;
  onEdit: () => void;
  onViewMetrics: () => void;
  onRefresh: () => void;
  sessionToken: string;
}

export default function BehaviorCard({
  behavior,
  onEdit,
  onViewMetrics,
  onRefresh,
  sessionToken,
}: BehaviorCardProps) {
  const theme = useTheme();
  const notifications = useNotifications();
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const handleDeleteClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setDeleteDialogOpen(true);
  };

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
    } catch (err) {
      notifications.show('Failed to delete behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
  };

  const metricsCount = behavior.metrics?.length || 0;
  const canDelete = metricsCount === 0;

  // Prepare chip sections
  const chipSections: ChipSection[] = [
    {
      chips: [
        ...behavior.metrics.slice(0, 3).map(metric => ({
          key: metric.id,
          icon: <AutoGraphIcon fontSize="small" />,
          label: metric.name,
          maxWidth: '150px',
        })),
        ...(metricsCount > 3
          ? [
              {
                key: 'more',
                label: `+${metricsCount - 3} more`,
              },
            ]
          : []),
      ],
    },
  ];

  // Top right actions
  const topRightActions = (
    <>
      {metricsCount > 0 && (
        <Tooltip title="View metrics">
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onViewMetrics();
            }}
            sx={{
              padding: theme.spacing(0.25),
              '& .MuiSvgIcon-root': {
                fontSize:
                  theme?.typography?.helperText?.fontSize || '0.75rem',
                color: 'currentColor',
              },
            }}
          >
            <AssessmentIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      )}
      <Tooltip title="Edit behavior">
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          sx={{
            padding: theme.spacing(0.25),
            '& .MuiSvgIcon-root': {
              fontSize:
                theme?.typography?.helperText?.fontSize || '0.75rem',
              color: 'currentColor',
            },
          }}
        >
          <EditIcon fontSize="inherit" />
        </IconButton>
      </Tooltip>
      {canDelete && (
        <Tooltip title="Delete behavior">
          <IconButton
            size="small"
            onClick={handleDeleteClick}
            sx={{
              padding: theme.spacing(0.25),
              '& .MuiSvgIcon-root': {
                fontSize:
                  theme?.typography?.helperText?.fontSize || '0.75rem',
                color: 'currentColor',
              },
            }}
          >
            <DeleteIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      )}
    </>
  );

  return (
    <>
      <EntityCard
        icon={<PsychologyIcon fontSize="medium" />}
        title={behavior.name}
        description={behavior.description || 'No description provided'}
        topRightActions={topRightActions}
        captionText={
          metricsCount > 0
            ? `${metricsCount} ${metricsCount === 1 ? 'Metric' : 'Metrics'}`
            : 'No metrics assigned'
        }
        chipSections={chipSections}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        isLoading={isDeleting}
        itemType="behavior"
        itemName={behavior.name}
      />
    </>
  );
}

